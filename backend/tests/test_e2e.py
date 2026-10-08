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
    from app.services.nlp.salary import net_to_gross_monthly

    # hh.ru указывает зарплату «на руки»: на платформе все суммы до вычета НДФЛ — пересчёт, исходное значение сохранено
    assert p["headline"] == g["headline"] and p["desired_salary_net"] == g["salary"]
    assert p["desired_salary"] == net_to_gross_monthly(g["salary"])
    assert set(p["work_formats"]) == g["formats"] and p["relocation"] == g["relocation"] and p["city"] == g["city"]
    assert abs(p["experience_years"] - g["months"] / 12) < 0.1
    assert [(e["company"], e["position"], e["start"]) for e in p["experience"]] == \
        [(e["company"], e["position"], e["start"]) for e in g["experience"]]
    assert g["university"] in p["education"][0]["title"] and p["education"][0]["year"] == g["edu_year"]
    assert {x["name"] for x in p["languages"]} == {n for n, _ in g["languages"]}
    assert p["about"] and g["about"][:30] in p["about"]
    assert set(p["skills"]) & g["skills"]


def _new_candidate(client, email: str, spec: str = "backend", lang: str = "python", grade: str = "junior") -> dict:
    r = client.post(f"{API}/auth/register", json={"email": email, "password": "secret-pass-1", "role": "candidate",
                                                  "consent_pd": True})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/auth/verify-email", json={"email": email, "code": r.json()["dev_code"]})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post(f"{API}/testing/survey", headers=h, json={
        "industries": ["Финтех и банки"], "specialization": spec, "language": lang, "experience": "1-2",
        "roles": ["developer"], "work_formats": ["remote"], "claimed_grade": grade, "fsp_participant": False})
    assert r.status_code == 200, r.text
    return h


def test_proctoring_two_strikes_terminate_with_penalty(client, monkeypatch):
    """Снимок экрана: 1-й — предупреждение, 2-й — тест завершается досрочно, нарушение фиксируется, оценка снижена."""
    from app.services.testing import service

    h = _new_candidate(client, "proctor@example.com")
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "junior"}).json()
    token = view["token"]
    assert view["proctoring"] == {"strikes": 0, "max_strikes": 2, "penalty": service.PROCTOR_PENALTY}
    for _ in range(3):
        q = view["question"]
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_correctly(token, q["id"])}).json()

    url = f"{API}/testing/sessions/{token}/proctoring"
    r = client.post(url, headers=h, json={"kind": "focus_loss", "away_ms": 4200}).json()
    assert r["action"] == "logged" and r["strikes"] == 0
    r = client.post(url, headers=h, json={"kind": "screenshot", "method": "PrintScreen"}).json()
    assert r["action"] == "warn" and r["strikes"] == 1 and r["view"]["status"] == "in_progress"
    # то же действие, пойманное вторым детектором (потеря фокуса после Win+Shift+S), — не второй страйк
    r = client.post(url, headers=h, json={"kind": "screenshot", "method": "blur-after-combo"}).json()
    assert r["action"] == "duplicate" and r["strikes"] == 1
    assert client.post(url, headers=h, json={"kind": "telepathy"}).status_code == 422

    monkeypatch.setattr(service, "PROCTOR_DEDUPE_SEC", 0)
    r = client.post(url, headers=h, json={"kind": "screenshot", "method": "Meta+Shift+S"}).json()
    assert r["action"] == "terminate" and r["strikes"] == 2
    res = r["view"]["result"]
    assert r["view"]["status"] == "completed"
    assert res["proctoring"]["violation"] == "screenshot" and res["proctoring"]["terminated"]
    assert res["proctoring"]["penalty"] == service.PROCTOR_PENALTY and res["proctoring"]["away_count"] == 1
    assert res["decision"] != "confirmed_strong" and not res["next_grade"]
    # задание, на котором зафиксировано нарушение, засчитано неверным
    assert res["review"][-1]["correct"] is False and len(res["review"]) == 4
    assert client.post(url, headers=h, json={"kind": "screenshot"}).status_code == 409

    hist = client.get(f"{API}/testing/history", headers=h).json()["sessions"]
    assert hist[0]["violation"] == "screenshot"
    notes = client.get(f"{API}/notifications", headers=h).json()
    assert any(n["kind"] == "test_violation" for n in (notes["items"] if isinstance(notes, dict) else notes))


def test_penalty_shifts_decision_and_time_depends_on_difficulty():
    from app.services.testing.cat import AnsweredItem, CatConfig, CatState, decide
    from app.services.testing.service import effective_time_limit

    st = CatState({"python": 1.0}, "junior", "python")
    for i in range(14):
        st.answered.append(AnsweredItem(f"f{i}", "python", 1.4, -1.2 + 0.2 * i, 0.0, i < 10))
    base, pen = decide(st, CatConfig()), decide(st, CatConfig(), 0.5)
    assert abs(pen["theta"] - (base["theta"] - 0.5)) < 0.002
    assert pen["p_above_lower"] < base["p_above_lower"] and pen["percentile"] < base["percentile"]
    assert pen["raw_theta"] == base["theta"] and "raw_theta" not in base
    # время: лёгкое задание — меньше базового, трудное — больше, в пределах −20 %…+35 %
    assert effective_time_limit(90, -1.8) == 70 and effective_time_limit(90, 0.0) == 90
    assert effective_time_limit(90, 1.8) == 115 and effective_time_limit(240, 3.0) == 325


def _pass_test(client, h, grade: str, resume_id: int = 0) -> dict:
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": grade, "resume_id": resume_id}).json()
    token = view["token"]
    for _ in range(50):
        if view["status"] != "in_progress":
            break
        q = view["question"]
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_correctly(token, q["id"])}).json()
    assert view["status"] == "completed"
    return view


def test_multiple_resumes_give_multiple_categories(client):
    """Несколько резюме — несколько категорий: у каждого резюме свой опрос, свой тест и своя категория; работодатель
    находит кандидата по нужной категории и приглашает по конкретному резюме."""
    h = _new_candidate(client, "multi@example.com", spec="backend", lang="python", grade="junior")
    client.post(f"{API}/candidate/consents", headers=h, json={"kind": "profile_publication", "granted": True})
    res = _pass_test(client, h, "junior")["result"]
    assert res["assigned_grade"] == "junior"

    body = {"industries": [], "language": "python", "experience": "lt1", "roles": [], "work_formats": [],
            "claimed_grade": "junior"}
    # одна специализация — одно резюме
    r = client.post(f"{API}/candidate/resumes", headers=h, json={**body, "specialization": "backend"})
    assert r.status_code == 409
    r = client.post(f"{API}/candidate/resumes", headers=h, json={
        **body, "specialization": "devops", "title": "DevOps-инженер", "skills": ["docker", "linux", "kubernetes"]})
    assert r.status_code == 201, r.text
    rid = r.json()["resume"]["id"]
    assert rid > 0 and r.json()["eligibility"]["ready"] and r.json()["eligibility"]["resume_id"] == rid
    # основной опрос не может «забрать» специализацию дополнительного резюме
    assert client.post(f"{API}/testing/survey", headers=h, json={**body, "specialization": "devops"}).status_code == 409

    view = _pass_test(client, h, "junior", rid)
    assert view["resume_id"] == rid and view["specialization"] == "devops"
    assert view["result"]["assigned_grade"] == "junior"
    resumes = client.get(f"{API}/candidate/resumes", headers=h).json()
    cats = {x["id"]: (x["category"]["specialization"], x["category"]["grade"]) for x in resumes}
    assert cats == {0: ("backend", "junior"), rid: ("devops", "junior")}
    # ограничения частоты — у каждой категории свои
    el = client.get(f"{API}/testing/eligibility?resume_id={rid}", headers=h).json()
    assert el["specialization"] == "devops" and el["current_grade"] == "junior"
    assert client.get(f"{API}/testing/eligibility?resume_id=999999", headers=h).status_code == 404
    hist = client.get(f"{API}/testing/history", headers=h).json()
    assert {s["resume_id"] for s in hist["sessions"]} == {0, rid}

    # работодатель: подборка DevOps находит кандидата по дополнительному резюме (кандидат — один раз)
    eh = login(client, "employer@demo.ru")
    sel = client.post(f"{API}/employer/selections", headers=eh, json={
        "text": "Ищем Junior DevOps-инженера: Docker, Kubernetes, Linux, CI/CD. Удалённо, до 200 000 ₽.",
        "title": "DevOps junior"}).json()
    cid = client.get(f"{API}/candidate/profile", headers=h).json()["id"]
    mine = [x for x in sel["results"] if x["id"] == cid]
    assert len(mine) == 1 and mine[0]["resume_id"] == rid
    card = client.get(f"{API}/employer/candidates/{cid}?resume_id={rid}", headers=eh).json()
    assert card["category"]["specialization"] == "devops" and card["resume_id"] == rid
    assert {x["specialization"] for x in card["resumes"]} == {"backend", "devops"}
    r = client.post(f"{API}/employer/invitations", headers=eh, json={
        "candidate_id": cid, "resume_id": rid, "title": "Junior DevOps", "message": "Приглашаем в команду платформы",
        "contact_method": "Telegram @hr", "salary_from": 150000, "salary_to": 190000})
    assert r.status_code == 201, r.text
    inv = client.get(f"{API}/candidate/invitations", headers=h).json()[0]
    assert inv["resume"]["resume_id"] == rid and inv["resume"]["specialization"] == "devops"

    # скрытое резюме не участвует в поиске; удалённое — исчезает из профиля
    client.put(f"{API}/candidate/resumes/{rid}", headers=h, json={"title": "DevOps-инженер", "skills": ["docker"],
                                                                   "visible": False})
    found = client.get(f"{API}/employer/candidates?specialization=devops&size=100", headers=eh).json()["results"]
    assert all(x["id"] != cid for x in found)
    assert client.get(f"{API}/employer/candidates/{cid}?resume_id={rid}", headers=eh).status_code == 404
    # лимит: основная + две дополнительные специализации
    assert client.post(f"{API}/candidate/resumes", headers=h, json={**body, "specialization": "qa"}).status_code == 201
    assert client.post(f"{API}/candidate/resumes", headers=h, json={**body, "specialization": "ml"}).status_code == 409
    assert client.delete(f"{API}/candidate/resumes/{rid}", headers=h).status_code == 200
    assert client.delete(f"{API}/candidate/resumes/0", headers=h).status_code == 409
    assert len(client.get(f"{API}/candidate/resumes", headers=h).json()) == 2


def _answer_by_difficulty(session_token: str, response_id: int, b_max: float):
    """Модель кандидата «уровня b_max»: решает задания легче b_max, на остальные отвечает «Не знаю»."""
    from app.core.db import SessionLocal
    from app.models import TestResponse

    with SessionLocal() as db:
        r = db.scalar(select(TestResponse).where(TestResponse.id == response_id))
        return r.answer_key["key"] if r.payload["irt"]["b"] < b_max else None


def _take_test(client, h, grade: str, b_max: float, resume_id: int = 0) -> dict:
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": grade, "resume_id": resume_id}).json()
    token = view["token"]
    for _ in range(50):
        if view["status"] != "in_progress":
            break
        q = view["question"]
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_by_difficulty(token, q["id"], b_max)}).json()
    assert view["status"] == "completed"
    return view


def test_unconfirmed_ranks_below_identical_confirmed():
    """Неподтверждённый грейд опускает кандидата: при той же θ совпадение грейда не засчитывается."""
    from app.core.db import utcnow
    from app.models import CandidateProfile
    from app.services.matching.ranking import Need, score_candidates

    base = dict(skills=["python", "sql"], domain_scores={}, work_formats=["remote"], city="Казань", open_to_offers=True,
                privacy={}, specialization="backend", primary_language="python", fsp_score=0.0, tasks_done=0,
                last_active_at=utcnow(), headline="Python-разработчик", about="", experience=[])
    conf = CandidateProfile(id=1, public_id="C-1", grade="middle", grade_specialization="backend", grade_theta=0.5,
                            grade_se=0.3, strength=0.345, **base)  # сила = 0.6 · положение θ в полосе Middle
    unc = CandidateProfile(id=2, public_id="C-2", unconfirmed_grade="middle", unconfirmed_theta=0.5, unconfirmed_se=0.3,
                           strength=0.0, **base)
    need = Need(specialization="backend", grades=["middle"], must_skills=["python"], nice_skills=[])
    a, b = sorted(score_candidates(need, [unc, conf]), key=lambda r: r["candidate_id"])
    assert a["grade_status"] == "confirmed" and b["grade_status"] == "unconfirmed"
    assert b["components"]["strength"] == a["components"]["strength"]  # та же θ — та же сила профиля
    assert b["components"]["category"] < a["components"]["category"] and b["score"] < a["score"]
    assert b["specialization"] == "backend" and b["claimed_grade"] == "middle" and b["measured_grade"] == "middle"
    assert "не подтверждён" in b["reasons"][0]["text"]


def test_unconfirmed_grade_shown_with_status_and_lower(client):
    """Тест не подтвердил грейд, а подтверждённого нет: кандидат не скрыт — работодатель видит его со статусом
    «не подтверждён» и после подтверждённых; кандидат может отключить показ; подтверждение грейда снимает статус."""
    h = _new_candidate(client, "unconfirmed@example.com", grade="middle")
    client.post(f"{API}/candidate/consents", headers=h, json={"kind": "profile_publication", "granted": True})
    res = _take_test(client, h, "middle", -0.3)["result"]  # уровень около Junior: Middle не подтверждается
    assert res["decision"] == "not_confirmed" and res["assigned_grade"] is None
    prof = client.get(f"{API}/candidate/profile", headers=h).json()
    cat = prof["category"]
    assert cat["status"] == "unconfirmed" and cat["grade"] is None and cat["claimed_grade"] == "middle"
    assert cat["specialization"] == "backend" and cat["measured_grade"] in ("intern", "junior", "middle")
    dash = client.get(f"{API}/candidate/dashboard", headers=h).json()
    assert dash["visible_to_employers"] and dash["visible_as_unconfirmed"]

    eh = login(client, "employer@demo.ru")

    def search(**kw):
        rows, page = [], 1
        while True:
            r = client.get(f"{API}/employer/candidates", headers=eh,
                           params={"specialization": "backend", "size": 100, "page": page, **kw}).json()
            rows += r["results"]
            if page * 100 >= r["total"]:
                return rows
            page += 1

    rows = search()
    mine = next(r for r in rows if r["id"] == prof["id"])
    assert mine["grade_status"] == "unconfirmed" and mine["claimed_grade"] == "middle" and mine["grade"] is None
    statuses = [r["grade_status"] for r in rows]
    assert statuses == sorted(statuses, key=lambda s: s == "unconfirmed")  # неподтверждённые — после подтверждённых
    assert all(r["id"] != prof["id"] for r in search(confirmed_only=True))
    assert any(r["id"] == prof["id"] for r in search(grades="middle"))  # фильтр грейда — по заявленному

    sel = client.post(f"{API}/employer/selections", headers=eh, json={
        "text": "Ищем Middle Python-разработчика: Python, SQL, Docker, REST API. Удалённо, 150 000 – 300 000 ₽."}).json()
    cat_mid = next(c for c in sel["categories"] if c["specialization"] == "backend" and c["grade"] == "middle")
    assert cat_mid["unconfirmed"] >= 1
    full = client.get(f"{API}/employer/selections/{sel['id']}", headers=eh, params={"size": 100, "grades": "middle"}).json()
    unconfirmed_rows = [r for r in full["results"] if r["grade_status"] == "unconfirmed"]
    assert unconfirmed_rows and all("не подтверждён" in r["reasons"][0]["text"] for r in unconfirmed_rows)
    assert all(r["claimed_grade"] == "middle" or r["measured_grade"] == "middle" for r in unconfirmed_rows)
    row = next((r for r in full["results"] if r["id"] == prof["id"]), None)
    if row is not None:  # пул ограничен лучшими 150 — кандидат может не войти, если подтверждённых много
        assert row["grade_status"] == "unconfirmed"
    only = client.get(f"{API}/employer/selections/{sel['id']}", headers=eh,
                      params={"size": 100, "confirmed_only": True}).json()
    assert all(r["grade_status"] == "confirmed" for r in only["results"])

    card = client.get(f"{API}/employer/candidates/{prof['id']}", headers=eh).json()
    assert card["category"]["status"] == "unconfirmed" and card["category"]["claimed_grade_name"] == "Middle"
    r = client.post(f"{API}/employer/invitations", headers=eh, json={
        "candidate_id": prof["id"], "title": "Junior Python-разработчик", "message": "Предлагаем начать с Junior.",
        "salary_from": 120000, "salary_to": 160000, "contact_method": "Telegram @technopulse_hr"})
    assert r.status_code == 201, r.text

    pv = client.get(f"{API}/candidate/profile", headers=h).json()["privacy"]
    client.put(f"{API}/candidate/privacy", headers=h, json={**pv, "show_unconfirmed": False})
    assert all(r["id"] != prof["id"] for r in search())  # кандидат отключил показ
    assert not client.get(f"{API}/candidate/dashboard", headers=h).json()["visible_to_employers"]

    res2 = _pass_test(client, h, "junior")["result"]  # подтвердил уровень ниже — статус снят
    assert res2["assigned_grade"] == "junior"
    cat = client.get(f"{API}/candidate/profile", headers=h).json()["category"]
    assert cat["status"] == "confirmed" and cat["grade"] == "junior" and cat["claimed_grade"] is None


def test_sync_unconfirmed_restores_status_from_history(client):
    """Данные до появления статуса: при старте статус восстанавливается из истории тестов (идемпотентно)."""
    from app.core.db import SessionLocal
    from app.models import User
    from app.services.testing.service import clear_unconfirmed, sync_unconfirmed

    h = _new_candidate(client, "legacy@example.com", grade="senior")
    _take_test(client, h, "senior", -0.3)
    with SessionLocal() as db:
        cand = db.scalar(select(User).where(User.email == "legacy@example.com")).candidate
        assert cand.unconfirmed_grade == "senior"
        clear_unconfirmed(cand)  # как в базе, созданной до появления статуса
        db.commit()
        assert sync_unconfirmed(db) >= 1
        db.refresh(cand)
        assert cand.unconfirmed_grade == "senior" and cand.unconfirmed_theta is not None
        assert sync_unconfirmed(db) == 0


def test_guest_candidate_express_test(client, monkeypatch):
    """«Попробовать как кандидат»: аккаунт в один клик и экспресс-тест на 8 коротких заданий — пробная оценка уровня
    без категории; ограничения полного теста на него не действуют, статистика банка не меняется."""
    from sqlalchemy import func

    from app.core.db import SessionLocal
    from app.models import ItemStat
    from app.services.testing import service

    body = {"specialization": "backend", "language": "python", "claimed_grade": "middle", "consent_pd": True}
    assert client.post(f"{API}/auth/guest", json={**body, "consent_pd": False}).status_code == 422
    assert client.post(f"{API}/auth/guest", json={**body, "language": "swift"}).status_code == 422
    r = client.post(f"{API}/auth/guest", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "candidate"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    prof = client.get(f"{API}/candidate/profile", headers=h).json()
    assert prof["specialization"] == "backend" and prof["claimed_grade"] == "middle" and not prof["consent_publish"]

    with SessionLocal() as db:
        exposures = db.scalar(select(func.sum(ItemStat.exposures)))
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "middle", "mode": "express"}).json()
    assert view["mode"] == "express" and view["max_items"] == 8
    token, n = view["token"], 0
    while view["status"] == "in_progress":
        q = view["question"]
        assert q["time_limit"] <= 165  # задания с коротким ответом: базовый лимит до 2 минут
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_correctly(token, q["id"])}).json()
        n += 1
    res = view["result"]
    assert n == 8 and res["express"] and res["assigned_grade"] is None and "decision" not in res
    assert abs(sum(res["grade_probs"].values()) - 1) < 0.02 and res["estimated_grade"] in ("middle", "senior")
    assert res["review"] and all(x["correct"] for x in res["review"])
    with SessionLocal() as db:
        assert db.scalar(select(func.sum(ItemStat.exposures))) == exposures  # экспресс не входит в статистику банка

    cat = client.get(f"{API}/candidate/profile", headers=h).json()["category"]
    assert cat["grade"] is None and cat["status"] is None  # категория не присвоена и не «не подтверждена»
    el = client.get(f"{API}/testing/eligibility", headers=h).json()
    assert next(g for g in el["grades"] if g["grade"] == "middle")["allowed"]  # попытка полного теста не потрачена
    assert client.get(f"{API}/testing/history", headers=h).json()["sessions"][0]["mode"] == "express"
    assert client.post(f"{API}/testing/sessions/{token}/accept-suggested", headers=h).status_code == 409

    monkeypatch.setattr(service, "EXPRESS_PER_DAY", 1)
    r = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "junior", "mode": "express"})
    assert r.status_code == 429


def test_guest_accounts_expire(client):
    """Гостевые аккаунты удаляются через 2 дня вместе с данными."""
    from datetime import timedelta

    from app.core.db import SessionLocal, utcnow
    from app.models import CandidateProfile, User

    body = {"specialization": "qa", "language": "python", "claimed_grade": "junior", "consent_pd": True}
    first = client.post(f"{API}/auth/guest", json=body).json()["user"]["email"]
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == first))
        u.created_at = utcnow() - timedelta(days=3)
        db.commit()
    assert client.post(f"{API}/auth/guest", json=body).status_code == 201
    with SessionLocal() as db:  # id в SQLite могут переиспользоваться — проверяем по адресу гостя
        assert db.scalar(select(User).where(User.email == first)) is None
        assert db.scalar(select(CandidateProfile).where(CandidateProfile.contact_email == first)) is None


def test_guest_account_cannot_publish_or_apply(client):
    """Демо-аккаунт не попадает к работодателям: публикацию профиля и отклики сервер отклоняет; интерфейс узнаёт
    гостя по /auth/me, а кнопку «без регистрации» показывает по флагу из /public/stats."""
    body = {"specialization": "backend", "language": "python", "claimed_grade": "junior", "consent_pd": True}
    h = {"Authorization": f"Bearer {client.post(f'{API}/auth/guest', json=body).json()['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=h).json()["guest"] is True
    assert client.get(f"{API}/auth/me", headers=login(client, "candidate@demo.ru")).json()["guest"] is False
    assert client.get(f"{API}/public/stats").json()["guest_mode"] is True
    r = client.post(f"{API}/candidate/consents", headers=h, json={"kind": "profile_publication", "granted": True})
    assert r.status_code == 409
    assert not client.get(f"{API}/candidate/profile", headers=h).json()["consent_publish"]
    vid = client.get(f"{API}/vacancies", headers=h).json()[0]["id"]
    assert client.post(f"{API}/vacancies/{vid}/apply", headers=h, json={}).status_code == 409


def test_lower_grade_can_be_accepted_from_same_test(client):
    """Не подтвердил Middle, но тест уверенно показал уровень не ниже Junior — Junior можно принять сразу."""
    from app.services.testing.cat import AnsweredItem, CatConfig, CatState, decide

    st = CatState({"python": 1.0}, "middle", "python")
    for i in range(20):
        b = -2.0 + 0.2 * i
        st.answered.append(AnsweredItem(f"f{i}", "python", 1.6, b, 0.0, b < -0.4))
    res = decide(st, CatConfig())
    assert res["decision"] == "not_confirmed" and res["suggested_grade"] == "junior"
    assert res["suggested_assignable"] and res["suggested_p"] >= 0.8

    h = _new_candidate(client, "lower@example.com", grade="middle")
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "middle"}).json()
    token = view["token"]
    for _ in range(50):
        if view["status"] != "in_progress":
            break
        q = view["question"]
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_by_difficulty(token, q["id"], -0.3)}).json()
    res = view["result"]
    assert res["decision"] == "not_confirmed" and res["assigned_grade"] is None
    if not res["suggested_assignable"]:  # граница случайна: проверяем, что принять нельзя
        assert client.post(f"{API}/testing/sessions/{token}/accept-suggested", headers=h).status_code == 409
        return
    r = client.post(f"{API}/testing/sessions/{token}/accept-suggested", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["assigned_grade"] == res["suggested_grade"]
    prof = client.get(f"{API}/candidate/profile", headers=h).json()
    assert prof["category"]["grade"] == res["suggested_grade"]
    assert client.post(f"{API}/testing/sessions/{token}/accept-suggested", headers=h).status_code == 409


def test_strong_result_unlocks_next_level_on_demand_once(client):
    """Уверенный результат не запускает следующий тест сам: уровень выше доступен без ожидания, когда кандидат
    готов (без срока), — одна попытка, дальше действуют обычные ограничения (месяц)."""
    from datetime import timedelta

    from app.core.db import SessionLocal
    from app.models import TestSession

    h = _new_candidate(client, "strong@example.com", grade="junior")
    view = _pass_test(client, h, "junior")
    res = view["result"]
    assert res["decision"] == "confirmed_strong" and res["next_grade"] == "middle"
    el = client.get(f"{API}/testing/eligibility", headers=h).json()
    assert el["cooldown_days"] == 30 and el["in_progress"] is None  # следующий тест сам не начался
    # срока нет: и через 20 дней тест уровнем выше доступен без ожидания
    with SessionLocal() as db:
        s = db.scalar(select(TestSession).where(TestSession.token == view["token"]))
        s.started_at -= timedelta(days=20)
        s.finished_at -= timedelta(days=20)
        db.commit()
    by = {g["grade"]: g for g in client.get(f"{API}/testing/eligibility", headers=h).json()["grades"]}
    assert by["middle"]["allowed"] and "когда будете готовы" in by["middle"]["reason"]
    assert not by["senior"]["allowed"]  # смена грейда — не чаще раза в месяц
    # одна попытка: после неё — обычные ограничения
    v = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "middle"}).json()
    client.post(f"{API}/testing/sessions/{v['token']}/abandon", headers=h)
    by = {g["grade"]: g for g in client.get(f"{API}/testing/eligibility", headers=h).json()["grades"]}
    assert not by["middle"]["allowed"] and "через 30 дней" in by["middle"]["reason"]


def test_new_feature_refinements(client):
    """Подсказка грейда по резюме, разбор PDF без сохранения, избранное по резюме, отметка о честности теста
    в карточке работодателя и админ-список нарушений прокторинга."""
    import random

    from app.seed.synthetic import generate_population
    from validation.nlp_validation import _gold, hh_pdf

    h = _new_candidate(client, "hint@example.com")
    client.put(f"{API}/candidate/profile", headers=h, json={"full_name": "Подсказкин Пётр", "experience_years": 3.5,
                                                             "headline": "Python-разработчик"})
    hint = client.get(f"{API}/testing/grade-hint", headers=h).json()
    assert hint["grade"] == "middle" and "стаж" in hint["reason"]

    rng = random.Random(3)
    c = next(x for x in generate_population(20, seed=5) if x.experience)
    pdf = hh_pdf(c, _gold(c, rng), rng)
    r = client.post(f"{API}/candidate/resume?save=false", headers=h, files={"file": ("cv.pdf", pdf, "application/pdf")})
    assert r.status_code == 200 and r.json()["full_name"]
    assert client.get(f"{API}/candidate/profile", headers=h).json()["resume_filename"] is None  # профиль не тронут

    # кандидат из теста про несколько резюме: категория подтверждена чисто, есть резюме QA без категории
    mh = login(client, "multi@example.com", "secret-pass-1")
    cid = client.get(f"{API}/candidate/profile", headers=mh).json()["id"]
    qa = next(x for x in client.get(f"{API}/candidate/resumes", headers=mh).json() if x["specialization"] == "qa")
    eh = login(client, "employer@demo.ru")
    card = client.get(f"{API}/employer/candidates/{cid}", headers=eh).json()
    # «оракул» отвечает мгновенно → детектор «слишком быстрых ответов» → нейтрально (без отметки «без нарушений»)
    assert card["integrity"]["status"] in ("clean", "neutral")
    assert client.post(f"{API}/employer/shortlist", headers=eh, json={"candidate_id": cid, "resume_id": qa["id"]}).json()["resume_id"] == qa["id"]
    item = next(x for x in client.get(f"{API}/employer/shortlist", headers=eh).json() if x["candidate"]["id"] == cid)
    assert item["candidate"]["resume_id"] == qa["id"] and item["candidate"]["shortlisted"]

    ah = login(client, "admin@demo.ru")
    data = client.get(f"{API}/admin/integrity", headers=ah).json()
    assert data["summary"]["violations"] >= 1
    s = next(x for x in data["sessions"] if x["violation"] == "screenshot")
    assert s["terminated"] and any(e["kind"] == "screenshot" for e in s["events"])
    assert client.get(f"{API}/admin/integrity", headers=eh).status_code == 403



def test_category_from_penalized_session_is_marked_for_employer(client, monkeypatch):
    """Категория, присвоенная тестом, завершённым за повторное нарушение, отмечается для работодателя."""
    from app.services.testing import service

    monkeypatch.setattr(service, "PROCTOR_DEDUPE_SEC", 0)
    h = _new_candidate(client, "penalized@example.com", grade="junior")
    client.post(f"{API}/candidate/consents", headers=h, json={"kind": "profile_publication", "granted": True})
    view = client.post(f"{API}/testing/sessions", headers=h, json={"grade": "junior"}).json()
    token = view["token"]
    for _ in range(9):
        q = view["question"]
        view = client.post(f"{API}/testing/sessions/{token}/answer", headers=h,
                           json={"response_id": q["id"], "answer": _answer_correctly(token, q["id"])}).json()
    assert view["status"] == "in_progress"
    url = f"{API}/testing/sessions/{token}/proctoring"
    client.post(url, headers=h, json={"kind": "screenshot"})
    res = client.post(url, headers=h, json={"kind": "screenshot"}).json()["view"]["result"]
    assert res["proctoring"]["terminated"] and res["assigned_grade"] == "junior"
    cid = client.get(f"{API}/candidate/profile", headers=h).json()["id"]
    card = client.get(f"{API}/employer/candidates/{cid}", headers=login(client, "employer@demo.ru")).json()
    assert card["integrity"]["status"] == "penalized"


def test_code_task_sandbox_flow(client):
    """Задача с кодом: эталон проверяет тесты, кандидат запускает примеры в песочнице, отправка — на всех тестах
    (скрытые не раскрываются), антиплагиат отмечает переименованную копию."""
    eh = login(client, "employer@demo.ru")
    reference = ("def normalize_phones(phones):\n    seen, out = set(), []\n    for p in phones:\n"
                 "        d = ''.join(ch for ch in p if ch.isdigit())\n        if len(d) == 10:\n            d = '7' + d\n"
                 "        if len(d) != 11 or d[0] not in '78':\n            continue\n        n = '+7' + d[1:]\n"
                 "        if n not in seen:\n            seen.add(n)\n            out.append(n)\n    return out\n")
    tests = [{"args": [["8 (900) 123-45-67"]], "expected": ["+79001234567"]},
             {"args": [["+7 900 123 45 67", "89001234567"]], "expected": ["+79001234567"], "name": "дубли"},
             {"args": [["9001234567", "123"]], "expected": ["+79001234567"], "hidden": True},
             {"args": [[]], "expected": [], "hidden": True}]
    body = {"title": "Нормализация телефонов", "description": "Приведите номера к формату +7XXXXXXXXXX, уберите дубли.",
            "specialization": "backend", "kind": "code", "code_language": "python", "entrypoint": "normalize_phones",
            "starter_code": "def normalize_phones(phones):\n    pass\n", "tests": tests, "reference_solution": reference}
    # ошибка в ожидаемом ответе ловится эталоном
    bad = {**body, "tests": tests[:2] + [{"args": [["9001234567"]], "expected": ["+70000000000"], "hidden": True}]}
    r = client.post(f"{API}/employer/tasks", headers=eh, json=bad)
    assert r.status_code == 422 and "тест №3" in r.text
    assert client.post(f"{API}/employer/tasks", headers=eh, json={**body, "tests": tests[:2]}).status_code == 422
    r = client.post(f"{API}/employer/tasks", headers=eh, json=body)
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["hidden_count"] == 2 and len(task["examples"]) == 2 and task["reference_solution"]

    from app.core.db import SessionLocal
    from app.models import TaskAssignment

    users = [_new_candidate(client, f"coder{i}@example.com") for i in range(2)]
    ids = []
    with SessionLocal() as db:
        for h in users:
            cid = client.get(f"{API}/candidate/profile", headers=h).json()["id"]
            ta = TaskAssignment(task_id=task["id"], candidate_id=cid)
            db.add(ta)
            db.flush()
            ids.append(ta.id)
        db.commit()

    h1, h2 = users
    view = next(t for t in client.get(f"{API}/candidate/tasks", headers=h1).json() if t["id"] == ids[0])
    assert view["task"]["code_language"] == "python" and "reference_solution" not in view["task"]
    assert all("expected" in x for x in view["task"]["examples"]) and view["task"]["hidden_count"] == 2
    assert client.post(f"{API}/candidate/tasks/{ids[0]}/submit", headers=h1, json={"answer": "текстовый ответ"}).status_code == 409

    wrong = "def normalize_phones(phones):\n    return phones\n"
    r = client.post(f"{API}/candidate/tasks/{ids[0]}/run", headers=h1, json={"code": wrong}).json()
    assert r["status"] == "ok" and r["total"] == 2 and r["passed"] == 0 and r["tests"][0]["actual"] == ["8 (900) 123-45-67"]
    assert client.post(f"{API}/candidate/tasks/{ids[0]}/run", headers=h1, json={"code": wrong}).status_code == 429
    import time as _t

    _t.sleep(2.1)
    r = client.post(f"{API}/candidate/tasks/{ids[0]}/run", headers=h1, json={"code": "def normalize_phones(p) return"}).json()
    assert r["status"] == "compile_error" and "SyntaxError" in r["error"]

    _t.sleep(2.1)
    done = client.post(f"{API}/candidate/tasks/{ids[0]}/submit-code", headers=h1,
                       json={"code": reference, "signals": {"pastes": [{"chars": 40}], "away_count": 1}}).json()
    assert done["status"] == "submitted" and done["results"]["passed"] == 4 and done["results"]["hidden_total"] == 2
    hidden = [x for x in done["results"]["tests"] if x["hidden"]]
    assert hidden and all("args" not in x and "expected" not in x for x in hidden)  # скрытые не раскрываются

    copy = reference.replace("seen", "used").replace("out", "res").replace("n =", "num =").replace("(n)", "(num)") \
        .replace("n not in", "num not in")
    done2 = client.post(f"{API}/candidate/tasks/{ids[1]}/submit-code", headers=h2, json={"code": copy}).json()
    assert done2["results"]["passed"] == 4

    subs = client.get(f"{API}/employer/tasks/submissions?status=submitted", headers=eh).json()
    mine = {s["id"]: s for s in subs if s["id"] in ids}
    assert mine[ids[1]]["plagiarism"]["similarity"] >= 0.85
    assert mine[ids[0]]["plagiarism"]["candidate_public_id"] == mine[ids[1]]["candidate"]["public_id"]
    assert mine[ids[0]]["signals"]["pasted_chars"] == 40 and mine[ids[0]]["auto_score"] == 1.0
    assert all("expected" in x for x in mine[ids[0]]["results"]["tests"])  # работодатель видит скрытые тесты


def test_seeded_code_task_demo(client):
    """Демо-стенд: у ТехноПульс есть задача с кодом и три решения (копию отмечает антиплагиат), демо-кандидату она
    предложена — эталон и скрытые тесты кандидат не видит."""
    eh = login(client, "employer@demo.ru")
    task = next(t for t in client.get(f"{API}/employer/tasks", headers=eh).json()
                if t["title"] == "Нормализация телефонных номеров")
    assert task["kind"] == "code" and task["counts"]["submitted"] == 3 and task["hidden_count"] == 4
    subs = [s for s in client.get(f"{API}/employer/tasks/submissions?status=submitted", headers=eh).json()
            if s["task"]["id"] == task["id"]]
    assert sorted(s["results"]["passed"] for s in subs) == [2, 6, 6]
    flagged = [s for s in subs if s["plagiarism"]]
    assert len(flagged) == 2 and all(s["plagiarism"]["similarity"] >= 0.85 for s in flagged)
    assert max(s["signals"]["paste_share"] for s in flagged) == 1.0
    ch = login(client, "candidate@demo.ru")
    offered = next(t for t in client.get(f"{API}/candidate/tasks", headers=ch).json() if t["task"]["id"] == task["id"])
    assert offered["status"] == "offered" and len(offered["task"]["examples"]) == 2
    assert "reference_solution" not in offered["task"] and "tests" not in offered["task"]


def test_sandbox_isolation_limits():
    """Бесконечный цикл обрывается по таймауту, ошибки и синтаксис не роняют сервис."""
    from app.services.sandbox.runner import run

    assert run("python", "def f(x):\n    while True:\n        pass\n", "f", [[1]], 800)["status"] == "timeout"
    assert run("python", "import sys\ndef f(x):\n    sys.exit(3)\n", "f", [[1]])["results"][0]["ok"] is False
    assert run("python", "def f(x):\n    return f(x)\n", "f", [[1]])["results"][0]["error"].startswith("RecursionError")
    assert run("python", "x = 1", "os.system", [[1]])["status"] == "error"  # имя функции проверяется
    assert run("ruby", "puts 1", "f", [[1]])["status"] == "error"
