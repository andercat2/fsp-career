"""Черновики заданий от LLM: генерация (модель подменяется), автоматические проверки и самопроверка, решения эксперта,
пилотный статус принятого вопроса в банке, демо-режим без модели, права доступа."""
import pytest
from sqlalchemy import select

from tests.conftest import login

API = "/api/v1/admin/item-drafts"

GOOD = {"topic": "Сравнение с NULL", "prompt": "Что вернёт запрос SELECT * FROM t WHERE x = NULL, если в столбце x есть NULL?",
        "code": None, "code_lang": None, "correct": "Ни одной строки",
        "distractors": ["Строки, где x равен NULL", "Все строки таблицы", "Ошибку выполнения"],
        "explanation": "Сравнение с NULL через = даёт UNKNOWN, нужен IS NULL."}


@pytest.fixture
def fake_llm(monkeypatch):
    """Подменяет модель: вопросы по очереди из списка, самопроверка — по флагу; фоновая задача — синхронно."""
    from app.services import llm
    from app.services.testing import drafting

    state = {"questions": [], "review": {"verdict": "ok", "also_correct": [], "issues": []}, "calls": 0}

    def chat_json(messages, schema, temperature=0.7):
        state["calls"] += 1
        if "verdict" in schema["properties"]:
            return state["review"]
        return state["questions"].pop(0)

    monkeypatch.setattr(llm, "status", lambda force=False: {"available": True, "model": "test-model", "reason": None})
    monkeypatch.setattr(llm, "chat_json", chat_json)
    monkeypatch.setattr(drafting, "_submit", lambda fn, *a: fn(*a))
    return state


def _generate(client, h, **kw):
    body = {"specialization": "backend", "domain": "sql", "level": 3, "count": 1} | kw
    r = client.post(f"{API}/batches", headers=h, json=body)
    assert r.status_code == 202, r.text
    return client.get(f"{API}/batches/{r.json()['id']}", headers=h).json()


def test_drafts_require_admin(client):
    h = login(client, "employer@demo.ru")
    assert client.get(f"{API}/options", headers=h).status_code == 403
    assert client.post(f"{API}/batches", headers=h, json={"specialization": "backend", "level": 3, "count": 1}).status_code == 403


def test_generate_review_and_accept_as_is(client, fake_llm):
    """Черновик → проверка экспертом → пилотное семейство банка; кандидаты его видят, на оценку оно не влияет."""
    from app.core.db import SessionLocal
    from app.models import ItemStat
    from app.services.testing.bank import BY_DOMAIN, REGISTRY

    h = login(client, "admin@demo.ru")
    opts = client.get(f"{API}/options", headers=h).json()
    assert opts["llm"]["mode"] == "llm" and len(opts["levels"]) == 5
    backend = next(s for s in opts["specializations"] if s["code"] == "backend")
    assert {"sql", "python", "java", "go", "javascript"} <= {d["code"] for d in backend["domains"]}

    fake_llm["questions"] = [dict(GOOD)]
    b = _generate(client, h)
    assert b["status"] == "done" and b["done"] == 1 and b["source"] == "llm" and b["model"] == "test-model"
    pending = client.get(API, headers=h).json()
    d = next(x for x in pending["items"] if x["batch_id"] == b["id"])
    assert d["options"][d["correct"]] == GOOD["correct"] and sorted(d["options"]) == sorted([GOOD["correct"], *GOOD["distractors"]])
    assert d["checks"]["review"]["verdict"] == "ok" and not [c for c in d["checks"]["auto"] if c["level"] == "error"]

    r = client.post(f"{API}/{d['id']}/accept", headers=h)
    assert r.status_code == 200, r.text
    fid = r.json()["family_id"]
    assert fid == f"llm.sql.{d['id']}" and r.json()["status"] == "accepted" and not r.json()["edited"]
    fam = REGISTRY[fid]
    assert fam in BY_DOMAIN["sql"] and fam.pretest and not fam.parametric
    with SessionLocal() as db:
        assert db.get(ItemStat, fid).status == "pretest"  # пилотное: без влияния на оценку до калибровки
    v = fam.render(42)
    assert {o["text"] for o in v.options} == {GOOD["correct"], *GOOD["distractors"]}
    assert next(o["text"] for o in v.options if o["id"] == v.key) == GOOD["correct"]
    assert client.post(f"{API}/{d['id']}/accept", headers=h).status_code == 409  # решение уже принято
    acc = client.get(f"{API}?status=accepted", headers=h).json()
    assert next(x for x in acc["items"] if x["id"] == d["id"])["pilot"]["status"] == "pretest"


def test_expert_edits_question_and_answer(client, fake_llm):
    h = login(client, "admin@demo.ru")
    fake_llm["questions"] = [dict(GOOD, topic="Индексы", prompt="Какой индекс ускорит запрос WHERE a = 1 AND b > 5?")]
    fake_llm["review"] = {"verdict": "problem", "also_correct": [0, 1, 2, 3], "issues": ["Варианты не относятся к вопросу"]}
    b = _generate(client, h)
    d = next(x for x in client.get(API, headers=h).json()["items"] if x["batch_id"] == b["id"])
    rv = d["checks"]["review"]
    assert rv["verdict"] == "problem" and d["correct"] not in rv["also_correct"] and rv["issues"]

    edit = {"topic": "Составные индексы", "level": 4, "prompt": "Какой индекс лучше всего ускорит запрос WHERE a = 1 AND b > 5?",
            "code": "SELECT * FROM t WHERE a = 1 AND b > 5;", "code_lang": "sql",
            "options": ["(a, b)", "(b, a)", "Отдельные индексы по a и по b", "Индекс по b"], "correct": 0,
            "explanation": "Сначала столбец с равенством, затем столбец с диапазоном."}
    bad = dict(edit, options=["(a, b)", "(a, b)", "x", "y"])
    assert client.post(f"{API}/{d['id']}/accept", headers=h, json=bad).status_code == 422  # одинаковые варианты
    r = client.post(f"{API}/{d['id']}/accept", headers=h, json=edit)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["edited"] and out["original"]["topic"] == "Индексы" and out["level"] == 4
    from app.services.testing.bank import REGISTRY

    fam = REGISTRY[out["family_id"]]
    v = fam.render(3)
    assert fam.level == 4 and v.code_lang == "sql" and next(o["text"] for o in v.options if o["id"] == v.key) == "(a, b)"


def test_reject_and_checks(client, fake_llm):
    h = login(client, "admin@demo.ru")
    leak = dict(GOOD, topic="Подзапросы", prompt="Верно ли, что SELECT MAX(price) FROM products вернёт максимальную цену?",
                correct="SELECT MAX(price) FROM products", distractors=["Нет", "Только для целых чисел", "Только с GROUP BY"])
    fake_llm["questions"] = [leak, {"topic": "x", "prompt": "", "correct": "", "distractors": []}]
    b = _generate(client, h, count=2)
    assert b["done"] == 1 and b["failed"] == 1 and "неполный" in b["error"]  # второй ответ модели непригоден
    d = next(x for x in client.get(API, headers=h).json()["items"] if x["batch_id"] == b["id"])
    assert "leak" in {c["code"] for c in d["checks"]["auto"]}  # правильный ответ виден в условии
    r = client.post(f"{API}/{d['id']}/reject", headers=h, json={"reason": "Неверный правильный ответ"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert client.post(f"{API}/{d['id']}/reject", headers=h, json={"reason": "Другое"}).status_code == 409
    assert client.post(f"{API}/batches", headers=h, json={"specialization": "backend", "domain": "react", "level": 3,
                                                          "count": 1}).status_code == 422  # раздел не из теста Backend


def test_demo_mode_without_llm(client, monkeypatch):
    """Без модели — черновики из заранее сгенерированного набора, с пометкой источника."""
    from app.services import llm
    from app.services.testing import drafting

    monkeypatch.setattr(drafting, "_submit", lambda fn, *a: fn(*a))
    monkeypatch.setattr(llm, "status", lambda force=False: {"available": False, "model": "x", "reason": "нет сервиса"})
    item = {"domain": "linux", "level": 2, "specialization": "devops", "topic": "Права доступа",
            "prompt": "Что означает право доступа 755 у каталога?", "code": None, "code_lang": None,
            "correct": "Владелец — всё, остальные — чтение и вход", "distractors": ["Все — всё", "Только владелец", "Никто"],
            "explanation": "7 = rwx, 5 = r-x.", "model": "qwen3:14b",
            "review": {"verdict": "ok", "also_correct": [], "issues": [],
                       "options": ["Все — всё", "Владелец — всё, остальные — чтение и вход", "Только владелец", "Никто"]}}
    monkeypatch.setattr(drafting, "_demo_set", lambda: {"model": "qwen3:14b", "items": [item]})
    h = login(client, "admin@demo.ru")
    assert client.get(f"{API}/options", headers=h).json()["llm"]["mode"] == "demo"
    b = _generate(client, h, specialization="devops", domain="linux", level=2)
    assert b["source"] == "demo" and b["done"] == 1
    d = next(x for x in client.get(API, headers=h).json()["items"] if x["batch_id"] == b["id"])
    assert d["source"] == "demo" and d["model"] == "qwen3:14b" and d["options"][d["correct"]] == item["correct"]


def test_accepted_drafts_survive_restart(client, fake_llm):
    """Принятые черновики хранятся в БД и при старте снова регистрируются в банке."""
    from app.core.db import SessionLocal
    from app.models import ItemDraft
    from app.services.testing import drafting
    from app.services.testing.bank import BY_DOMAIN, REGISTRY

    h = login(client, "admin@demo.ru")
    fake_llm["questions"] = [dict(GOOD, topic="Транзакции", prompt="Какой уровень изоляции защищает от фантомного чтения?",
                                  correct="SERIALIZABLE", distractors=["READ COMMITTED", "READ UNCOMMITTED", "Никакой"])]
    b = _generate(client, h, domain="databases")
    did = next(x for x in client.get(API, headers=h).json()["items"] if x["batch_id"] == b["id"])["id"]
    fid = client.post(f"{API}/{did}/accept", headers=h).json()["family_id"]
    fam = REGISTRY.pop(fid)  # «перезапуск»: банк из кода не знает о черновиках
    BY_DOMAIN["databases"].remove(fam)
    with SessionLocal() as db:
        assert drafting.load_drafted_families(db) >= 1
        assert db.scalar(select(ItemDraft).where(ItemDraft.family_id == fid)).status == "accepted"
    assert fid in REGISTRY and REGISTRY[fid].pretest
