"""Публичные эндпоинты: методика и результаты валидации, статистика банка заданий, стенд оценки ранжирования
(для проверки жюри на собственном наборе пар «вакансия — кандидат»), служебные эндпоинты администратора."""
import json
import threading
import time
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.api.deps import DB, Admin
from app.core.config import BASE_DIR, settings
from app.models import CandidateProfile, CandidateResume, Company, Invitation, ItemStat, TestSession, Vacancy
from app.schemas import EvalDatasetIn, EvalRankIn, Message
from app.services.fsp.scoring import fsp_score
from app.services.matching.evaluation import evaluate_dataset
from app.services.matching.profile import W_FSP, W_TEST, test_position
from app.services.matching.ranking import Need, score_candidates
from app.services.nlp.vacancy_parser import parse_need
from app.services.reference.taxonomy import DOMAINS, GRADE_NAMES, SPEC_NAMES
from app.services.testing.bank import REGISTRY, bank_summary
from app.services.testing.service import FULL_ONLY, calibrate_pretest

router = APIRouter(tags=["Публичное: методика и оценка"])
REPORTS = BASE_DIR / "validation" / "reports"


REPORT_NAMES = ("cat_validation", "matching_validation", "nlp_validation")
STATS_TTL_SEC = 30
_stats_cache: dict = {"at": 0.0, "value": None}
_cache_lock = threading.Lock()


@lru_cache(maxsize=4)
def _methodology_json(key: tuple) -> bytes:
    """Отчёты валидации + сводка банка, сериализованные один раз: страница «Методика» и главная читают их часто."""
    out = {}
    for name in REPORT_NAMES:
        p = Path(REPORTS / f"{name}.json")
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    out["bank"] = {"total_families": len(REGISTRY), "parametric": sum(f.parametric for f in list(REGISTRY.values())),
                   "domains": {k: {**v, "name": DOMAINS.get(k, k)} for k, v in bank_summary().items()}}
    return json.dumps(out, ensure_ascii=False, default=str).encode("utf-8")


@router.get("/public/methodology", summary="Результаты валидации механик тестирования и подбора")
def methodology():
    key = tuple((REPORTS / f"{n}.json").stat().st_mtime if (REPORTS / f"{n}.json").exists() else 0
                for n in REPORT_NAMES) + (len(REGISTRY),)
    return Response(_methodology_json(key), media_type="application/json",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("/public/stats", summary="Статистика платформы")
def stats(db: DB):
    """Счётчики для главной страницы; кэш на 30 секунд в процессе — главную открывает каждый посетитель."""
    now = time.monotonic()
    with _cache_lock:
        if _stats_cache["value"] is not None and now - _stats_cache["at"] < STATS_TTL_SEC:
            return _stats_cache["value"]
    value = _stats(db)
    with _cache_lock:
        _stats_cache.update(at=now, value=value)
    return value


def _stats(db) -> dict:
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return {
        "candidates": count(CandidateProfile), "categorized": count(CandidateProfile, CandidateProfile.grade.is_not(None)),
        "extra_categories": count(CandidateResume, CandidateResume.grade.is_not(None)),
        "with_fsp": count(CandidateProfile, CandidateProfile.fsp_id.is_not(None)), "companies": count(Company),
        "vacancies": count(Vacancy, Vacancy.is_published.is_(True)),
        "tests": count(TestSession, TestSession.status == "completed", FULL_ONLY),
        "invitations": count(Invitation), "accepted": count(Invitation, Invitation.status == "accepted"),
        "item_families": len(REGISTRY), "guest_mode": settings.guest_mode,
    }


@router.post("/eval/rank", summary="Стенд оценки: ранжирование переданных кандидатов под текст вакансии",
             description="Без сохранения данных. Позволяет проверить механику подбора на собственном наборе пар "
                         "«вакансия — кандидат» (метрики: доля релевантных в топе, nDCG).")
def eval_rank(data: EvalRankIn):
    parsed = parse_need(data.vacancy_text, data.vacancy_title)
    need = Need.from_dict(parsed | {"text": data.vacancy_text, "title": data.vacancy_title})
    cands = []
    for i, ec in enumerate(data.candidates):
        c = CandidateProfile(id=i + 1, public_id=ec.id, grade=ec.grade, grade_specialization=ec.specialization,
                             grade_theta=ec.theta, skills=ec.skills, verified_skills=ec.verified_skills or [],
                             desired_salary=ec.desired_salary, work_formats=ec.work_formats, city=ec.city,
                             fsp_profile={"achievements": ec.fsp_achievements} if ec.fsp_achievements else None,
                             about=ec.text, domain_scores={}, open_to_offers=True, tasks_done=0, privacy={})
        c.fsp_score = fsp_score(c.fsp_profile, c.grade_specialization)
        c.strength = round(W_TEST * test_position(c) + W_FSP * c.fsp_score, 4)
        cands.append(c)
    ranked = score_candidates(need, cands)
    return {"need": parsed, "ranking": [{"id": r["public_id"], "score": r["score"], "match": r["match"],
                                         "components": r["components"], "reasons": r["reasons"]} for r in ranked]}


@router.post("/eval/dataset", summary="Стенд оценки: выдача и метрики на наборе пар «вакансия — кандидат»",
             description="Проверка подбора на собственных данных жюри или работодателя, без сохранения. По каждой "
                         "вакансии строится выдача тем же ранжированием, что в продукте, и считаются доля релевантных "
                         "в топе (P@k), nDCG@k и MRR — рядом с поиском по ключевым словам (TF-IDF) на тех же данных. "
                         "Кандидат задаётся категорией по тесту (specialization + grade) или только текстом резюме — "
                         "тогда категорию определяет NLP со статусом «не подтверждён». Страница: /evaluate.",
             responses={422: {"model": Message}})
def eval_dataset(data: EvalDatasetIn):
    return evaluate_dataset(data)


@router.get("/admin/items", tags=["Администрирование"], summary="Статистика банка заданий: экспозиция и дрейф")
def items(_: Admin, db: DB):
    rows = db.scalars(select(ItemStat).order_by(ItemStat.exposures.desc()))
    return [{"family_id": r.family_id, "status": r.status, "a": r.a, "b": r.b, "c": r.c, "exposures": r.exposures,
             "correct": r.correct, "expected": round(r.expected_correct, 2), "drift_z": round(r.drift_z, 2),
             "domain": REGISTRY[r.family_id].domain if r.family_id in REGISTRY else None} for r in rows]


@router.post("/admin/items/calibrate", tags=["Администрирование"], summary="Откалибровать пилотные задания")
def calibrate(_: Admin, db: DB):
    return calibrate_pretest(db)


@router.get("/admin/integrity", tags=["Администрирование"],
            summary="Честность тестирования: нарушения прокторинга, перепроверка, флаги детекторов")
def integrity(_: Admin, db: DB, limit: int = 300):
    """Сессии, требующие внимания: страйки прокторинга (снимок экрана, печать, копирование), досрочное завершение,
    ответы «чужого варианта» (перепроверка), person-fit и слишком быстрые ответы на трудные задания."""
    rows = db.execute(select(TestSession, CandidateProfile.public_id)
                      .join(CandidateProfile, CandidateProfile.id == TestSession.candidate_id)
                      .where(TestSession.status.in_(["completed", "abandoned", "in_progress"]))
                      .order_by(TestSession.started_at.desc()).limit(5000))
    out = []
    for s, public_id in rows:
        pr = s.proctoring or {}
        res = s.result or {}
        flags = (res.get("integrity") or {}).get("flags") or []
        review = bool(res.get("review_required"))
        if not (pr.get("strikes") or pr.get("away_count") or flags or review):
            continue
        out.append({
            "token": s.token, "candidate": public_id, "candidate_id": s.candidate_id, "resume_id": s.resume_id or 0,
            "specialization": s.specialization, "specialization_name": SPEC_NAMES.get(s.specialization),
            "target_grade": s.target_grade, "target_grade_name": GRADE_NAMES.get(s.target_grade), "status": s.status,
            "decision": res.get("decision"), "assigned_grade": res.get("assigned_grade"),
            "strikes": pr.get("strikes", 0), "violation": pr.get("violation"), "terminated": bool(pr.get("terminated")),
            "away_count": pr.get("away_count", 0), "away_sec": round(pr.get("away_ms", 0) / 1000),
            "flags": flags, "review_required": review, "penalty": res.get("penalty", 0.0),
            "events": (pr.get("events") or [])[-30:], "started_at": s.started_at, "finished_at": s.finished_at,
        })
        if len(out) >= limit:
            break
    return {"total": len(out), "summary": {
        "violations": sum(1 for x in out if x["violation"]), "warnings": sum(1 for x in out if x["strikes"] == 1),
        "review": sum(1 for x in out if x["review_required"]), "flagged": sum(1 for x in out if x["flags"])},
        "sessions": out}
