"""Сквозной сценарий из ТЗ: регистрация соискателя → опрос → тест → категория → работодатель находит категорию
и выходит на контакт → кандидат принимает приглашение → контакты раскрываются. Плюс правила видимости."""
from sqlalchemy import select

from tests.conftest import login

API = "/api/v1"


def _answer_correctly(session_token: str, response_id: int):
    """Тестовый «оракул»: берёт ключ ответа из БД (в продукте кандидату он недоступен)."""
    from app.core.db import SessionLocal
    from app.models import TestResponse

    with SessionLocal() as db:
        r = db.scalar(select(TestResponse).where(TestResponse.id == response_id))
        return r.answer_key["key"]


def test_full_candidate_and_employer_flow(client):
    # 1. регистрация и подтверждение e-mail
    r = client.post(f"{API}/auth/register", json={"email": "new.dev@example.com", "password": "secret-pass-1",
                                                  "role": "candidate", "consent_pd": True})
    assert r.status_code == 201, r.text
    code = r.json()["dev_code"]
    assert client.post(f"{API}/auth/login", json={"email": "new.dev@example.com", "password": "secret-pass-1"}).status_code == 403
    r = client.post(f"{API}/auth/verify-email", json={"email": "new.dev@example.com", "code": code})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 2. профиль, согласие на публикацию
    r = client.put(f"{API}/candidate/profile", headers=h, json={
        "full_name": "Тестов Тест", "city": "Казань", "work_formats": ["remote"], "desired_salary": 200000,
        "headline": "Python-разработчик", "skills": ["python", "postgresql", "fastapi", "docker"],
        "telegram": "@test_dev", "phone": "+7 900 000-00-00"})
    assert r.status_code == 200, r.text
    assert client.post(f"{API}/candidate/consents", headers=h, json={"kind": "profile_publication", "granted": True}).status_code == 200

    # 3. опрос
    r = client.post(f"{API}/testing/survey", headers=h, json={
        "industries": ["Финтех и банки"], "specialization": "backend", "language": "python", "experience": "2-5",
        "roles": ["developer"], "work_formats": ["remote"], "claimed_grade": "middle", "fsp_participant": False})
    assert r.status_code == 200, r.text
    assert any(g["grade"] == "middle" and g["allowed"] for g in r.json()["eligibility"]["grades"])

    # 4. адаптивный тест: отвечаем верно → грейд подтверждается
    r = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "middle"})
    assert r.status_code == 200, r.text
    view = r.json()
    token = view["token"]
    assert "answer_key" not in str(view["question"]) and "irt" not in view["question"]
    for _ in range(50):
        if view["status"] != "in_progress":
            break
        q = view["question"]
        key = _answer_correctly(token, q["id"])
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": key}).json()
    assert view["status"] == "completed"
    res = view["result"]
    assert res["decision"] in ("confirmed", "confirmed_strong")
    assert res["assigned_grade"] == "middle"
    assert 12 <= res["n_items"] <= 24

    # повторно тот же уровень — нельзя (ограничение частоты); ниже текущего — нельзя
    el = client.get(f"{API}/testing/eligibility", headers=h).json()
    by = {g["grade"]: g for g in el["grades"]}
    assert not by["middle"]["allowed"] and not by["junior"]["allowed"]

    prof = client.get(f"{API}/candidate/profile", headers=h).json()
    assert prof["category"]["grade"] == "middle"
    assert "python" in prof["verified_skills"]
    cand_id = prof["id"]

    # 5. работодатель: подборка по свободному описанию потребности
    eh = login(client, "employer@demo.ru")
    r = client.post(f"{API}/employer/selections", headers=eh, json={
        "text": "Ищем Middle Python backend разработчика: FastAPI, PostgreSQL, Docker. Удалённо, до 300 000 ₽.",
        "title": "Python backend"})
    assert r.status_code == 201, r.text
    sel = r.json()
    assert sel["need"]["specialization"] == "backend"
    assert any(c["primary"] and c["grade"] == "middle" for c in sel["categories"])
    assert sel["results"] and all(x["reasons"] for x in sel["results"])
    # уточнение фильтром не теряет исходную подборку
    r2 = client.get(f"{API}/employer/selections/{sel['id']}?has_fsp=true", headers=eh).json()
    assert r2["total_in_selection"] == sel["total_in_selection"] and r2["total"] <= sel["total"]

    # 6. до принятия приглашения контакты скрыты
    card = client.get(f"{API}/employer/candidates/{cand_id}", headers=eh).json()
    assert card["contacts"] is None and card["name_hidden"]

    # приглашение без вилки — ошибка валидации
    bad = client.post(f"{API}/employer/invitations", headers=eh, json={
        "candidate_id": cand_id, "title": "Python-разработчик", "message": "Приглашаем на интервью к нам в команду",
        "contact_method": "Telegram @hr"})
    assert bad.status_code == 422
    r = client.post(f"{API}/employer/invitations", headers=eh, json={
        "candidate_id": cand_id, "title": "Python-разработчик", "message": "Приглашаем на интервью к нам в команду",
        "contact_method": "Telegram @hr", "salary_from": 220000, "salary_to": 280000})
    assert r.status_code == 201, r.text
    inv_id = r.json()["id"]

    # 7. кандидат видит условия (ЗП) до начала общения, открывает и принимает
    invs = client.get(f"{API}/candidate/invitations", headers=h).json()
    assert invs[0]["salary_from"] == 220000 and invs[0]["status"] == "sent" and invs[0]["company_contacts"] is None
    assert client.get(f"{API}/candidate/invitations/{inv_id}", headers=h).json()["status"] == "viewed"
    acc = client.post(f"{API}/candidate/invitations/{inv_id}/accept", headers=h).json()
    assert acc["status"] == "accepted" and acc["company_contacts"]["telegram"]

    # 8. теперь контакты раскрыты работодателю
    card = client.get(f"{API}/employer/candidates/{cand_id}", headers=eh).json()
    assert card["contacts_unlocked"] and card["contacts"]["telegram"] == "@test_dev"
    assert card["display_name"] == "Тестов Тест"


def test_candidate_cannot_see_others(client):
    h = login(client, "candidate@demo.ru")
    other = login(client, "newbie@demo.ru")
    invs = client.get(f"{API}/candidate/invitations", headers=h).json()
    assert invs
    assert client.get(f"{API}/candidate/invitations/{invs[0]['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/employer/candidates/1", headers=h).status_code == 403


def test_candidate_without_fsp_is_ranked(client):
    eh = login(client, "employer@demo.ru")
    sel = client.post(f"{API}/employer/selections", headers=eh, json={"vacancy_id": 1}).json()
    no_fsp = [x for x in sel["results"] if not x["fsp_linked"]]
    assert no_fsp, "кандидаты без ФСП должны присутствовать в выдаче"
    assert any("Нет истории ФСП" in r["text"] for r in no_fsp[0]["reasons"])


def test_vacancy_flow_and_test_preview(client):
    eh = login(client, "employer@demo.ru")
    parsed = client.post(f"{API}/employer/vacancies/parse", headers=eh, json={
        "title": "QA-инженер", "text": "Ищем тестировщика: тест-дизайн, Postman, SQL, Jira. Junior. 90-120 тыс руб, офис"}).json()
    assert parsed["specialization"] == "qa"
    r = client.post(f"{API}/employer/vacancies", headers=eh, json={
        "title": "QA-инженер", "description": "Тест-дизайн и API", "specialization": "qa", "grades": ["junior"],
        "must_skills": parsed["must_skills"], "salary_from": 90000, "salary_to": 120000, "is_published": True})
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    prev = client.get(f"{API}/employer/vacancies/{vid}/test-preview", headers=eh).json()
    assert prev["items"] and prev["blueprint"][0]["domain"] == "testing_theory"
    variants = prev["uniqueness_demo"]["variants"]
    assert len({str(v["answer"]) + v["prompt"] + str(v["code"]) for v in variants}) >= 2

    ch = login(client, "candidate@demo.ru")
    vacs = client.get(f"{API}/vacancies", headers=ch).json()
    assert any(v["id"] == vid for v in vacs)
    a = client.post(f"{API}/vacancies/{vid}/apply", headers=ch, json={"cover_letter": "Хочу к вам"})
    assert a.status_code == 200, a.text
    assert client.post(f"{API}/vacancies/{vid}/apply", headers=ch, json={}).status_code == 409
    apps = client.get(f"{API}/employer/vacancies/{vid}/applications", headers=eh).json()
    assert apps and apps[0]["candidate"]["contacts_unlocked"]  # откликнулся сам → контакты доступны


def test_pdf_generation(client):
    h = login(client, "candidate@demo.ru")
    r = client.get(f"{API}/candidate/profile/pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_resume_parsing():
    from app.services.nlp.resume_parser import parse_resume_text

    text = """Сидорова Мария Андреевна
Frontend-разработчик
Москва, готова к переезду
+7 (916) 123-45-67, maria.s@mail.ru, telegram: @maria_front
Опыт работы 4 года 2 месяца
Март 2022 — настоящее время
ООО «Веб Студия»
Frontend-разработчик
React, TypeScript, Redux, Jest. Наставничество стажёров, код-ревью.
Сентябрь 2020 — Февраль 2022
ООО «Старт»
Junior верстальщик
HTML, CSS, JavaScript.
Образование: МГТУ им. Баумана, бакалавр
Ответственная, быстро учусь, командная работа."""
    p = parse_resume_text(text)
    assert p["full_name"].startswith("Сидорова Мария")
    assert p["email"] == "maria.s@mail.ru" and p["phone"] == "+7 916 123-45-67" and p["telegram"] == "@maria_front"
    assert {"react", "typescript", "redux", "jest"} <= set(p["skills"])
    assert abs(p["experience_years"] - 4.17) < 0.1
    assert p["claimed_grade"] == "middle"
    assert "mentoring" in p["roles"] and "code_review" in p["roles"]
    assert p["specialization"] == "frontend"
    assert p["city"] == "Москва"


def test_resume_parsing_hh_layout():
    """Экспорт hh.ru: двухколоночная вёрстка (даты и подписи слева, содержимое справа) — все ключевые поля."""
    import random

    from app.seed.synthetic import generate_population
    from app.services.nlp.resume_parser import parse_resume_pdf
    from validation.nlp_validation import _gold, hh_pdf

    rng = random.Random(7)
    c = next(x for x in generate_population(40, seed=11) if len(x.experience) >= 2)
    g = _gold(c, rng)
    _, p = parse_resume_pdf(hh_pdf(c, g, rng))
    assert p["source"] == "hh"
    assert p["full_name"] == g["full_name"] and p["email"] == g["email"] and p["telegram"] == g["telegram"]
    assert p["headline"] == g["headline"] and p["desired_salary"] == g["salary"]
    assert set(p["work_formats"]) == g["formats"] and p["relocation"] == g["relocation"] and p["city"] == g["city"]
    assert abs(p["experience_years"] - g["months"] / 12) < 0.1
    assert [(e["company"], e["position"], e["start"]) for e in p["experience"]] == \
        [(e["company"], e["position"], e["start"]) for e in g["experience"]]
    assert g["university"] in p["education"][0]["title"] and p["education"][0]["year"] == g["edu_year"]
    assert {x["name"] for x in p["languages"]} == {n for n, _ in g["languages"]}
    assert p["about"] and g["about"][:30] in p["about"]
    assert set(p["skills"]) & g["skills"]
