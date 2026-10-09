"""Стенд проверки подбора на наборе пар «вакансия — кандидат» (POST /eval/dataset, страница /evaluate)."""
import json
from pathlib import Path

import pytest

API = "/api/v1"
SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "public" / "eval-sample.json"

VACANCIES = [
    {"id": "py", "title": "Python-разработчик (Middle)",
     "text": "Ищем Python-разработчика уровня Middle: FastAPI, PostgreSQL, Docker. Удалённо, 250–320 тыс. руб."},
    {"id": "qa", "title": "QA-инженер (Junior)",
     "text": "Нужен QA-инженер Junior: тест-дизайн, Postman, SQL, Jira. Офис в Казани, 90–120 тыс. руб."},
]
CANDIDATES = [
    {"id": "c1", "specialization": "backend", "grade": "middle", "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"]},
    {"id": "c2", "text": "Backend-разработчик, Python. Опыт работы 3 года: FastAPI, PostgreSQL, Docker, Redis. Middle. "
                         "Москва, удалённо. Ожидания 260 000 руб."},
    {"id": "c3", "text": "Frontend-разработчик: React, TypeScript, Redux. Опыт 2 года. Junior. Санкт-Петербург, офис."},
    {"id": "c4", "specialization": "qa", "grade": "junior", "text": "QA-инженер: тест-дизайн, Postman, SQL, Jira. Казань."},
    {"id": "c5", "text": "Тестировщик: ручное тестирование, Postman, SQL, баг-трекинг в Jira. Опыт 1 год. Казань, офис."},
]


def test_eval_dataset_ranks_and_scores(client):
    labels = [{"vacancy": "py", "candidate": "c1", "relevance": 1}, {"vacancy": "py", "candidate": "c2", "relevance": 1},
              {"vacancy": "qa", "candidate": "c4", "relevance": 1}, {"vacancy": "qa", "candidate": "c5", "relevance": 1}]
    r = client.post(f"{API}/eval/dataset", json={"vacancies": VACANCIES, "candidates": CANDIDATES, "labels": labels, "k": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["threshold"] == 1  # бинарная разметка
    assert d["candidates"] == {"total": 5, "with_category": 2, "text_only": 3}
    py = next(v for v in d["vacancies"] if v["id"] == "py")
    assert py["need"]["specialization"] == "Backend-разработчик"
    top = [c["id"] for c in py["ours"]["top"]]
    assert top[0] in ("c1", "c2") and "c3" not in top[:2] and "c4" not in top  # фронтенд и QA вне категорий Python-вакансии
    assert next(c for c in py["ours"]["top"] if c["id"] == "c2")["category"].endswith("(из резюме, не подтверждён)")
    for system in ("ours", "keyword"):
        assert 0 <= d["summary"][system]["p_at_k"] <= 1 and 0 <= d["summary"][system]["ndcg"] <= 1
    assert d["summary"]["ours"]["mrr"] == 1.0


@pytest.mark.skipif(not SAMPLE.exists(), reason="пример набора лежит во frontend/public — в образе бэкенда его нет")
def test_eval_dataset_sample_beats_keyword_search(client):
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data.pop("about")
    d = client.post(f"{API}/eval/dataset", json=data).json()
    assert d["threshold"] == 2 and d["vacancies_scored"] == len(data["vacancies"])
    assert d["summary"]["ours"]["p_at_k"] > d["summary"]["keyword"]["p_at_k"] + 0.15
    assert d["summary"]["ours"]["ndcg"] > d["summary"]["keyword"]["ndcg"]


def test_eval_dataset_rejects_unknown_ids(client):
    r = client.post(f"{API}/eval/dataset", json={"vacancies": VACANCIES, "candidates": CANDIDATES,
                                                 "labels": [{"vacancy": "py", "candidate": "nobody", "relevance": 2}]})
    assert r.status_code == 422
