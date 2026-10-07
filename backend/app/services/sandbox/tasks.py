"""Задачи с кодом: прогон тестов работодателя в песочнице, автопроверка, антиплагиат и сигналы подсказок.

Работодатель задаёт функцию, шаблон, открытые тесты (примеры для кандидата) и скрытые тесты; эталонное решение
проверяет сами тесты при сохранении. Кандидат запускает свой код на открытых тестах сколько угодно (с ограничением
частоты), а при отправке решение прогоняется на всех тестах: автооценка — доля пройденных. По скрытым тестам кандидат
видит только «пройден / нет» — входы и ответы не раскрываются. Сравнение с ожидаемым — здесь, вне песочницы.
"""
from __future__ import annotations

import json
import math

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import utcnow
from app.models import Task, TaskAssignment
from app.services.sandbox import runner
from app.services.sandbox.antiplagiarism import THRESHOLD, similarity

RUN_INTERVAL_SEC = 2  # не чаще одного прогона в 2 секунды на задание
MAX_RUNS = 100


def _post_run(payload: dict, timeout: float) -> dict:
    url = settings.sandbox_url
    if url.startswith("unix://"):  # Docker-стенд: у песочницы нет сети, общий Unix-сокет на томе
        transport, base = httpx.HTTPTransport(uds=url.removeprefix("unix://")), "http://sandbox"
    else:
        transport, base = None, url.rstrip("/")
    with httpx.Client(transport=transport, timeout=timeout) as client:
        r = client.post(f"{base}/run", json=payload, headers={"X-Sandbox-Token": settings.sandbox_token})
        r.raise_for_status()
        return r.json()


def execute(language: str, code: str, entrypoint: str, inputs: list, time_limit_ms: int) -> dict:
    """Изолированный контейнер sandbox (SANDBOX_URL) или локальный подпроцесс — только для разработки и тестов."""
    if settings.sandbox_url:
        try:
            return _post_run({"language": language, "code": code, "entrypoint": entrypoint, "inputs": inputs,
                              "time_limit_ms": time_limit_ms}, time_limit_ms / 1000 + 20)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Песочница временно недоступна — попробуйте ещё раз через минуту") from exc
    if not settings.sandbox_local:
        raise HTTPException(503, "Песочница не настроена")
    return runner.run(language, code, entrypoint, inputs, time_limit_ms)


def same(actual, expected, tol: float = 1e-6) -> bool:
    """Сравнение результата с ожидаемым: числа — с допуском, списки и словари — поэлементно."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(same(a, e, tol) for a, e in zip(actual, expected, strict=True))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(same(actual[k], expected[k], tol) for k in expected)
    return actual == expected


def _canon(v):
    return sorted(v, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)) if isinstance(v, list) else v


def evaluate(spec, code: str, which: str = "all") -> dict:
    """spec — Task или схема с полями задачи. which: all | visible."""
    tests = [t if isinstance(t, dict) else t.model_dump() for t in (spec.tests or [])]
    sel = [(i, t) for i, t in enumerate(tests) if which == "all" or not t.get("hidden")]
    raw = execute(spec.code_language, code, spec.entrypoint, [t["args"] for _, t in sel], spec.time_limit_ms or 2000)
    items = []
    if raw.get("status") == "ok":
        unordered = (spec.compare or "exact") == "unordered"
        for (i, t), res in zip(sel, raw["results"], strict=True):
            actual = res.get("value")
            ok = bool(res.get("ok")) and (same(_canon(actual), _canon(t.get("expected"))) if unordered
                                          else same(actual, t.get("expected")))
            items.append({"index": i, "name": t.get("name"), "hidden": bool(t.get("hidden")), "passed": ok,
                          "args": t["args"], "expected": t.get("expected"), "actual": actual, "error": res.get("error"),
                          "stdout": res.get("stdout"), "ms": res.get("ms")})
    return {"status": raw.get("status"), "error": raw.get("error"), "stderr": (raw.get("stderr") or "")[-1000:],
            "duration_ms": raw.get("duration_ms"), "which": which, "at": utcnow().isoformat(), "tests": items,
            "passed": sum(x["passed"] for x in items), "total": len(sel),
            "hidden_passed": sum(x["passed"] for x in items if x["hidden"]),
            "hidden_total": sum(1 for _, t in sel if t.get("hidden"))}


def public_results(res: dict | None, for_employer: bool = False) -> dict | None:
    """Кандидату — полностью только открытые тесты; по скрытым — лишь «пройден / нет», без входов и ответов."""
    if not res or for_employer:
        return res
    tests = [x if not x["hidden"] else {"index": x["index"], "name": x.get("name"), "hidden": True,
                                         "passed": x["passed"], "error": "ошибка выполнения" if x.get("error") else None}
             for x in res.get("tests", [])]
    return {**res, "stderr": None, "tests": tests}


def check_reference(spec) -> dict:
    """Эталон работодателя должен проходить все тесты — иначе в тестах ошибка."""
    if not spec.reference_solution:
        return {"status": "skipped", "passed": 0, "total": len(spec.tests or []), "tests": []}
    return evaluate(spec, spec.reference_solution, "all")


def _limits(ta: TaskAssignment) -> None:
    now = utcnow()
    if ta.last_run_at and (now - ta.last_run_at).total_seconds() < RUN_INTERVAL_SEC:
        raise HTTPException(429, "Слишком часто: подождите пару секунд между запусками")
    if (ta.runs_count or 0) >= MAX_RUNS:
        raise HTTPException(429, f"Лимит запусков для задания исчерпан ({MAX_RUNS})")
    ta.last_run_at = now
    ta.runs_count = (ta.runs_count or 0) + 1


def run_examples(db: Session, ta: TaskAssignment, code: str) -> dict:
    task = ta.task
    if task.kind != "code":
        raise HTTPException(409, "Это задание без запуска кода")
    if ta.status != "offered":
        raise HTTPException(409, "Решение уже отправлено")
    _limits(ta)
    ta.code = code  # черновик сохраняется
    res = evaluate(task, code, "visible")
    db.commit()
    return public_results(res)


def _clean_signals(signals: dict | None, code: str) -> dict:
    s = signals or {}
    pastes = [{"chars": int(p.get("chars", 0))} for p in (s.get("pastes") or [])[:100] if isinstance(p, dict)]
    pasted = sum(p["chars"] for p in pastes)
    return {"pastes": len(pastes), "pasted_chars": pasted, "paste_share": round(min(1.0, pasted / max(1, len(code))), 2),
            "largest_paste": max((p["chars"] for p in pastes), default=0),
            "away_count": int(s.get("away_count") or 0), "elapsed_ms": int(s.get("elapsed_ms") or 0)}


def check_plagiarism(db: Session, ta: TaskAssignment) -> dict | None:
    task = ta.task
    best = None
    others = db.scalars(select(TaskAssignment).where(
        TaskAssignment.task_id == ta.task_id, TaskAssignment.id != ta.id, TaskAssignment.code.is_not(None),
        TaskAssignment.status.in_(["submitted", "reviewed"])))
    for o in others:
        sim = similarity(ta.code or "", o.code or "", task.code_language, task.starter_code)
        if sim < THRESHOLD:
            continue
        if best is None or sim > best["similarity"]:
            best = {"similarity": sim, "assignment_id": o.id, "candidate_public_id": o.candidate.public_id}
        if not o.plagiarism or (o.plagiarism.get("similarity") or 0) < sim:  # отмечаем и второе решение
            o.plagiarism = {"similarity": sim, "assignment_id": ta.id, "candidate_public_id": ta.candidate.public_id}
    if task.reference_solution:
        ref = similarity(ta.code or "", task.reference_solution, task.code_language, task.starter_code)
        if ref >= THRESHOLD:
            best = (best or {}) | {"reference_similarity": ref}
    return best


def submit(db: Session, ta: TaskAssignment, code: str, signals: dict | None) -> None:
    task = ta.task
    if task.kind != "code":
        raise HTTPException(409, "Это задание без запуска кода")
    if ta.status != "offered":
        raise HTTPException(409, "Решение уже отправлено")
    _limits(ta)
    res = evaluate(task, code, "all")
    ta.code = ta.answer = code
    ta.run_results = res
    ta.status, ta.submitted_at = "submitted", utcnow()
    ta.auto_score = round(res["passed"] / max(1, res["total"]), 3)
    ta.signals = _clean_signals(signals, code) | {"runs": ta.runs_count or 0}
    ta.plagiarism = check_plagiarism(db, ta)


def task_payload(t: Task, for_owner: bool = False) -> dict:
    """Поля задачи с кодом: кандидату — шаблон и открытые примеры; владельцу — всё, включая скрытые тесты и эталон."""
    if t.kind != "code":
        return {}
    tests = t.tests or []
    out = {"code_language": t.code_language, "entrypoint": t.entrypoint, "starter_code": t.starter_code,
           "time_limit_ms": t.time_limit_ms or 2000, "compare": t.compare or "exact",
           "examples": [{"index": i, "name": x.get("name"), "args": x["args"], "expected": x.get("expected")}
                        for i, x in enumerate(tests) if not x.get("hidden")],
           "hidden_count": sum(1 for x in tests if x.get("hidden"))}
    if for_owner:
        out |= {"tests": tests, "reference_solution": t.reference_solution}
    return out
