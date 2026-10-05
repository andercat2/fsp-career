"""Несколько резюме — несколько категорий.

Основное резюме — сам профиль кандидата (в API — id 0). Дополнительные резюме (CandidateResume) — под другие
специализации: у каждого свой опрос, свой адаптивный тест и своя категория «специализация × грейд», как того
требует ТЗ (категория определяется опросом и тестом, а не самоописанием). Общие данные — ФИО, контакты, город,
опыт, образование, ФСП, регулярные задания — берутся из профиля.

Для подбора резюме представлено объектом ResumeView с тем же набором атрибутов, что у профиля: ранжирование,
карточки и приглашения одинаково работают с основным и дополнительными резюме, а кандидат в выдаче показывается
один раз — с тем резюме, которое лучше подходит под потребность работодателя.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.models import CandidateProfile, CandidateResume
from app.services.reference.taxonomy import GRADE_NAMES, LANGUAGES, SPEC_NAMES

MAX_EXTRA_RESUMES = 2  # всего до трёх специализаций: основная + две дополнительные

# Поля опроса и категории: одинаковые имена у CandidateProfile и CandidateResume
CATEGORY_FIELDS = frozenset({
    "grade", "grade_specialization", "grade_theta", "grade_se", "grade_assigned_at", "grade_changed_at",
    "domain_scores", "verified_skills", "strength", "fsp_score", "specialization", "primary_language",
    "claimed_grade", "industries", "survey_completed_at",
})


class ResumeView:
    """Профиль кандидата «через» дополнительное резюме: категория, навыки, заголовок и ожидания по доходу — из
    резюме, всё остальное — из профиля. Только чтение: изменения пишутся в CandidateResume или CandidateProfile."""

    def __init__(self, cand: CandidateProfile, res: CandidateResume):
        object.__setattr__(self, "_cand", cand)
        object.__setattr__(self, "_res", res)

    def __getattr__(self, name: str):
        res: CandidateResume = object.__getattribute__(self, "_res")
        cand: CandidateProfile = object.__getattribute__(self, "_cand")
        if name in CATEGORY_FIELDS:
            return getattr(res, name)
        if name == "skills":
            return res.skills or []
        if name in ("headline", "resume_title"):
            return res.title or cand.headline
        if name == "about":
            return res.about or cand.about
        if name == "desired_salary":
            return res.desired_salary or cand.desired_salary
        if name == "resume_id":
            return res.id
        if name == "resume":
            return res
        return getattr(cand, name)

    def __setattr__(self, name: str, value) -> None:
        raise AttributeError("ResumeView только для чтения")

    def __repr__(self) -> str:
        return f"<ResumeView candidate={self._cand.id} resume={self._res.id} {self._res.specialization}>"


def base_candidate(prof) -> CandidateProfile:
    """Профиль кандидата за представлением резюме."""
    return object.__getattribute__(prof, "_cand") if isinstance(prof, ResumeView) else prof


def category_brief(prof) -> dict:
    """Категория резюме для карточек работодателя: без навыков и ожиданий."""
    import math

    th = prof.grade_theta
    return {"resume_id": prof.resume_id or 0, "title": prof.headline, "specialization": prof.grade_specialization,
            "specialization_name": SPEC_NAMES.get(prof.grade_specialization or ""), "grade": prof.grade,
            "grade_name": GRADE_NAMES.get(prof.grade or ""),
            "percentile": None if th is None else round(100 * 0.5 * (1 + math.erf(th / math.sqrt(2))), 1)}


def profiles(cand: CandidateProfile) -> list:
    """Все резюме кандидата как профили для подбора: основное + дополнительные."""
    return [cand, *(ResumeView(cand, r) for r in cand.resumes)]


def graded_profiles(cand: CandidateProfile) -> list:
    """Резюме с присвоенной категорией, которые кандидат показывает работодателям."""
    return [p for p in profiles(cand) if p.grade and (p.resume_id is None or p.resume.visible)]


def get_resume(cand: CandidateProfile, resume_id: int) -> CandidateResume:
    res = next((r for r in cand.resumes if r.id == resume_id), None)
    if res is None:
        raise HTTPException(404, "Резюме не найдено")
    return res


def profile_for(cand: CandidateProfile, resume_id: int | None):
    """0 / None — основное резюме (профиль), иначе — представление дополнительного резюме."""
    return ResumeView(cand, get_resume(cand, resume_id)) if resume_id else cand


def target_for(cand: CandidateProfile, resume_id: int | None):
    """Куда записываются ответы опроса и категория: профиль (основное резюме) или строка CandidateResume."""
    return get_resume(cand, resume_id) if resume_id else cand


def taken_specializations(cand: CandidateProfile, except_resume: int | None = None) -> set[str]:
    """Специализации, по которым у кандидата уже есть резюме: одна специализация — одно резюме и одна категория."""
    out = {s for s in (cand.specialization, cand.grade_specialization) if s} if except_resume != 0 else set()
    out |= {r.specialization for r in cand.resumes if r.id != except_resume}
    return out


def resume_summary(prof) -> dict:
    from app.services.candidates import category, skill_list  # локальный импорт: модули ссылаются друг на друга

    rid = prof.resume_id
    res = prof.resume if rid else None
    spec = prof.specialization
    return {
        "id": rid or 0, "main": rid is None,
        "title": prof.headline or (SPEC_NAMES.get(spec or "") if spec else None),
        "specialization": spec, "specialization_name": SPEC_NAMES.get(spec or ""),
        "primary_language": prof.primary_language, "language_name": LANGUAGES.get(prof.primary_language or ""),
        "claimed_grade": prof.claimed_grade, "claimed_grade_name": GRADE_NAMES.get(prof.claimed_grade or ""),
        "industries": prof.industries or [], "survey_completed_at": prof.survey_completed_at,
        "category": category(prof), "strength": round(prof.strength or 0.0, 3), "domains": prof.domain_scores or {},
        "skills": prof.skills or [], "skills_detail": skill_list(prof.skills or []),
        "verified_skills": prof.verified_skills or [], "desired_salary": prof.desired_salary,
        "about": res.about if res else prof.about, "visible": res.visible if res else True,
        "resume_filename": res.resume_filename if res else prof.resume_filename,
        "updated_at": res.updated_at if res else prof.updated_at,
    }


def resumes_overview(cand: CandidateProfile) -> list[dict]:
    return [resume_summary(p) for p in profiles(cand)]
