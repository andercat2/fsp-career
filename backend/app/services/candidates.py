"""Представления профиля кандидата: собственный (полный) и для работодателя (с учётом приватности).

Правило раскрытия контактов (ТЗ, п. 2.2): работодатель видит контакты кандидата только если кандидат принял
его приглашение или сам откликнулся на вакансию этой компании. До этого — анонимный код и подтверждённые данные.
"""
from __future__ import annotations

import math
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, CandidateProfile, Company, Invitation, TestSession, Vacancy
from app.models.candidate import DEFAULT_PRIVACY
from app.services.fsp.scoring import fsp_summary
from app.services.matching.profile import strength_breakdown
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import GRADE_NAMES, SPEC_NAMES
from app.services.resumes import (
    base_candidate,
    category_brief,
    category_spec,
    category_theta,
    grade_status,
    is_unconfirmed,
    measured_grade,
    resumes_overview,
    shown_profiles,
)


def new_public_id(db: Session) -> str:
    while True:
        pid = "C-" + secrets.token_hex(3).upper()
        if not db.scalar(select(CandidateProfile.id).where(CandidateProfile.public_id == pid)):
            return pid


def privacy(cand: CandidateProfile) -> dict:
    return {**DEFAULT_PRIVACY, **(cand.privacy or {})}


def percentile(theta: float | None) -> float | None:
    if theta is None:
        return None
    return round(100 * 0.5 * (1 + math.erf(theta / math.sqrt(2))), 1)


def category(cand: CandidateProfile) -> dict:
    """Категория резюме. status: confirmed — грейд подтверждён тестом; unconfirmed — тест не подтвердил заявленный
    грейд, а подтверждённого нет: работодатель видит кандидата с этим статусом и ниже подтверждённых."""
    unconfirmed = is_unconfirmed(cand)
    theta, se = category_theta(cand)
    spec = category_spec(cand)
    measured = measured_grade(cand) if unconfirmed else None
    return {
        "specialization": spec, "specialization_name": SPEC_NAMES.get(spec or ""),
        "grade": cand.grade, "grade_name": GRADE_NAMES.get(cand.grade or ""), "status": grade_status(cand),
        "claimed_grade": cand.unconfirmed_grade if unconfirmed else None,
        "claimed_grade_name": GRADE_NAMES.get(cand.unconfirmed_grade or "") if unconfirmed else None,
        "measured_grade": measured, "measured_grade_name": GRADE_NAMES.get(measured or "") if measured else None,
        "tested_at": cand.unconfirmed_at if unconfirmed else None,
        "theta": theta, "se": se, "percentile": percentile(theta),
        "assigned_at": cand.grade_assigned_at, "changed_at": cand.grade_changed_at,
    }


def contacts_unlocked(db: Session, cand: CandidateProfile, company_id: int) -> str | None:
    inv = db.scalar(select(Invitation.id).where(Invitation.candidate_id == cand.id, Invitation.company_id == company_id,
                                                Invitation.status == "accepted"))
    if inv:
        return "invitation_accepted"
    app_id = db.scalar(select(Application.id).join(Vacancy, Vacancy.id == Application.vacancy_id)
                       .where(Application.candidate_id == cand.id, Vacancy.company_id == company_id,
                              Application.status != "withdrawn"))
    if app_id:
        return "applied"
    return None


def skill_list(ids: list[str]) -> list[dict]:
    return [{"id": s, "name": SKILL_BY_ID[s].name if s in SKILL_BY_ID else s,
             "group": SKILL_BY_ID[s].group if s in SKILL_BY_ID else None} for s in ids or []]


def category_session(db: Session, prof) -> TestSession | None:
    """Сессия теста, по которой присвоена текущая категория резюме (основного или дополнительного), а при
    неподтверждённом грейде — тест, который грейд не подтвердил."""
    unconfirmed = is_unconfirmed(prof)
    if not prof.grade and not unconfirmed:
        return None
    q = (select(TestSession).where(TestSession.candidate_id == prof.id, TestSession.status == "completed",
                                   TestSession.specialization == category_spec(prof))
         .order_by(TestSession.finished_at.desc()))
    for s in db.scalars(q):
        if (s.resume_id or None) != (prof.resume_id or None):
            continue
        r = s.result or {}
        if (unconfirmed and r.get("decision") == "not_confirmed" and s.target_grade == prof.unconfirmed_grade) or                 (not unconfirmed and r.get("assigned_grade") == prof.grade):
            return s
    return None


def category_integrity(db: Session, prof) -> dict | None:
    """Что работодатель видит о честности теста, подтвердившего категорию: «без нарушений» — ни одного страйка
    прокторинга и ни одного флага детекторов; «оценка снижена» — тест завершён за повторное нарушение. Единичное
    предупреждение не показывается — это не нарушение, а повод для него."""
    s = category_session(db, prof)
    if s is None:
        return None
    pr = s.proctoring or {}
    flags = ((s.result or {}).get("integrity") or {}).get("flags") or []
    if pr.get("violation"):
        return {"status": "penalized", "text": "Оценка снижена за нарушение правил теста"}
    if not pr.get("strikes") and not flags:
        return {"status": "clean", "text": "Тест пройден без нарушений"}
    return {"status": "neutral", "text": None}


def own_view(cand: CandidateProfile) -> dict:
    return {
        "id": cand.id, "public_id": cand.public_id, "display_name": cand.full_name or cand.public_id,
        "full_name": cand.full_name, "headline": cand.headline, "about": cand.about, "city": cand.city,
        "relocation": cand.relocation, "work_formats": cand.work_formats or [], "desired_salary": cand.desired_salary,
        "experience_years": cand.experience_years, "experience": cand.experience or [], "education": cand.education or [],
        "skills": cand.skills or [], "skills_detail": skill_list(cand.skills), "verified_skills": cand.verified_skills or [],
        "roles": cand.roles or [], "soft_skills": cand.soft_skills or [], "languages": cand.languages or [],
        "links": cand.links or {},
        "contacts": {"email": cand.contact_email, "phone": cand.phone, "telegram": cand.telegram},
        "industries": cand.industries or [], "specialization": cand.specialization,
        "specialization_name": SPEC_NAMES.get(cand.specialization or ""), "primary_language": cand.primary_language,
        "claimed_grade": cand.claimed_grade, "survey_completed_at": cand.survey_completed_at,
        "category": category(cand), "test": {"domains": cand.domain_scores or {}},
        "fsp_id": cand.fsp_id, "fsp_linked_at": cand.fsp_linked_at, "fsp_synced_at": cand.fsp_synced_at,
        "fsp": fsp_summary(cand.fsp_profile, cand.grade_specialization or cand.specialization),
        "privacy": privacy(cand), "consent_pd": cand.consent_pd, "consent_publish": cand.consent_publish,
        "open_to_offers": cand.open_to_offers, "strength": strength_breakdown(cand),
        "tasks_done": cand.tasks_done, "resume_filename": cand.resume_filename,
        "created_at": cand.created_at, "updated_at": cand.updated_at,
        "resumes": resumes_overview(cand),
    }


def employer_view(db: Session, cand: CandidateProfile, company: Company | None) -> dict:
    pv = privacy(cand)
    unlocked = contacts_unlocked(db, cand, company.id) if company else None
    show_name = pv["show_name"] or bool(unlocked)
    experience = []
    for e in cand.experience or []:
        e2 = dict(e)
        if not (pv["show_companies"] or unlocked):
            e2["company"] = None
        experience.append(e2)
    fsp = fsp_summary(cand.fsp_profile, cand.grade_specialization) if (pv["show_fsp"] or unlocked) else \
        {"linked": bool(cand.fsp_id), "hidden": True, "achievements": [], "score": cand.fsp_score, "headline": None}
    view = {
        "id": cand.id, "public_id": cand.public_id,
        "display_name": cand.full_name if (show_name and cand.full_name) else f"Кандидат {cand.public_id}",
        "name_hidden": not show_name,
        "headline": cand.headline, "about": cand.about, "city": cand.city, "relocation": cand.relocation,
        "work_formats": cand.work_formats or [],
        "desired_salary": cand.desired_salary if (pv["show_salary"] or unlocked) else None,
        "salary_hidden": not (pv["show_salary"] or unlocked),
        "experience_years": cand.experience_years, "experience": experience, "education": cand.education or [],
        "skills": cand.skills or [], "skills_detail": skill_list(cand.skills), "verified_skills": cand.verified_skills or [],
        "roles": cand.roles or [], "soft_skills": cand.soft_skills or [], "languages": cand.languages or [],
        "category": category(cand), "test": {"domains": cand.domain_scores or {}}, "fsp": fsp,
        "strength": strength_breakdown(cand), "tasks_done": cand.tasks_done, "open_to_offers": cand.open_to_offers,
        "last_active_at": cand.last_active_at,
        "contacts_unlocked": bool(unlocked), "unlock_reason": unlocked,
        "contacts": ({"email": cand.contact_email, "phone": cand.phone, "telegram": cand.telegram,
                      "links": cand.links or {}} if unlocked else None),
        # резюме (категории) кандидата: работодатель может переключиться и пригласить по нужной
        "resume_id": cand.resume_id or 0, "resume_title": cand.headline,
        "integrity": category_integrity(db, cand),
        "resumes": [category_brief(p) for p in shown_profiles(base_candidate(cand))],
    }
    return view
