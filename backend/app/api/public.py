"""Публичные эндпоинты: методика и результаты валидации, статистика банка заданий, стенд оценки ранжирования
(для проверки жюри на собственном наборе пар «вакансия — кандидат»), служебные эндпоинты администратора."""
import json
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DB, Admin
from app.core.config import BASE_DIR
from app.models import CandidateProfile, Company, Invitation, ItemStat, TestSession, Vacancy
from app.schemas import EvalRankIn
from app.services.fsp.scoring import fsp_score
from app.services.matching.profile import W_FSP, W_TEST, test_position
from app.services.matching.ranking import Need, score_candidates
from app.services.nlp.vacancy_parser import parse_need
from app.services.reference.taxonomy import DOMAINS
from app.services.testing.bank import REGISTRY, bank_summary
from app.services.testing.service import calibrate_pretest

router = APIRouter(tags=["Публичное: методика и оценка"])
REPORTS = BASE_DIR / "validation" / "reports"


@router.get("/public/methodology", summary="Результаты валидации механик тестирования и подбора")
def methodology():
    out = {}
    for name in ("cat_validation", "matching_validation", "nlp_validation"):
        p = Path(REPORTS / f"{name}.json")
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    out["bank"] = {"total_families": len(REGISTRY), "parametric": sum(f.parametric for f in REGISTRY.values()),
                   "domains": {k: {**v, "name": DOMAINS.get(k, k)} for k, v in bank_summary().items()}}
    return out


@router.get("/public/stats", summary="Статистика платформы")
def stats(db: DB):
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return {
        "candidates": count(CandidateProfile), "categorized": count(CandidateProfile, CandidateProfile.grade.is_not(None)),
        "with_fsp": count(CandidateProfile, CandidateProfile.fsp_id.is_not(None)), "companies": count(Company),
        "vacancies": count(Vacancy, Vacancy.is_published.is_(True)), "tests": count(TestSession, TestSession.status == "completed"),
        "invitations": count(Invitation), "accepted": count(Invitation, Invitation.status == "accepted"),
        "item_families": len(REGISTRY),
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


@router.get("/admin/items", tags=["Администрирование"], summary="Статистика банка заданий: экспозиция и дрейф")
def items(_: Admin, db: DB):
    rows = db.scalars(select(ItemStat).order_by(ItemStat.exposures.desc()))
    return [{"family_id": r.family_id, "status": r.status, "a": r.a, "b": r.b, "c": r.c, "exposures": r.exposures,
             "correct": r.correct, "expected": round(r.expected_correct, 2), "drift_z": round(r.drift_z, 2),
             "domain": REGISTRY[r.family_id].domain if r.family_id in REGISTRY else None} for r in rows]


@router.post("/admin/items/calibrate", tags=["Администрирование"], summary="Откалибровать пилотные задания")
def calibrate(_: Admin, db: DB):
    return calibrate_pretest(db)
