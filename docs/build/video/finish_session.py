"""Завершить сессию теста ответами по шаблону (1 — верно по ключу, 0 — «не знаю»). Запуск внутри контейнера бэкенда:
docker compose exec -T backend python - <token> <pattern> < finish_session.py — для скриншотов и видео документации."""
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import TestSession
from app.services.testing import service

token, pattern = sys.argv[1], sys.argv[2]
with SessionLocal() as db:
    sess = db.scalar(select(TestSession).where(TestSession.token == token))
    i = 0
    while sess.status == "in_progress" and i < 40:
        resp = service.current_response(sess)
        ok = pattern[i % len(pattern)] == "1"
        service.submit_answer(db, sess, resp.id, resp.answer_key["key"] if ok else None)
        i += 1
    r = sess.result or {}
    print("answered", i, "estimated", r.get("estimated_grade"), "probs", r.get("grade_probs"), "theta", r.get("theta"))
