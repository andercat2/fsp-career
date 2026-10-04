"""Представления профиля кандидата: собственный (полный) и для работодателя (с учётом приватности).

Правило раскрытия контактов (ТЗ, п. 2.2): работодатель видит контакты кандидата только если кандидат принял
его приглашение или сам откликнулся на вакансию этой компании. До этого — анонимный код и подтверждённые данные.
"""
from __future__ import annotations

import math
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, CandidateProfile, Company, Invitation, Vacancy
from app.models.candidate import DEFAULT_PRIVACY
from app.services.fsp.scoring import fsp_summary
from app.services.matching.profile import strength_breakdown
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import GRADE_NAMES, SPEC_NAMES


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
    return {
        "specialization": cand.grade_specialization, "specialization_name": SPEC_NAMES.get(cand.grade_specialization or ""),
        "grade": cand.grade, "grade_name": GRADE_NAMES.get(cand.grade or ""),
        "theta": cand.grade_theta, "se": cand.grade_se, "percentile": percentile(cand.grade_theta),
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


def own_view(cand: CandidateProfile) -> dict:
    return {
        "id": cand.id, "public_id": cand.public_id, "display_name": cand.full_name or cand.public_id,
        "full_name": cand.full_name, "headline": cand.headline, "about": cand.about, "city": cand.city,
        "relocation": cand.relocation, "work_formats": cand.work_formats or [], "desired_salary": cand.desired_salary,
        "experience_years": cand.experience_years, "experience": cand.experience or [], "education": cand.education or [],
        "skills": cand.skills or [], "skills_detail": skill_list(cand.skills), "verified_skills": cand.verified_skills or [],
        "roles": cand.roles or [], "soft_skills": cand.soft_skills or [], "links": cand.links or {},
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
        "roles": cand.roles or [], "soft_skills": cand.soft_skills or [],
        "category": category(cand), "test": {"domains": cand.domain_scores or {}}, "fsp": fsp,
        "strength": strength_breakdown(cand), "tasks_done": cand.tasks_done, "open_to_offers": cand.open_to_offers,
        "last_active_at": cand.last_active_at,
        "contacts_unlocked": bool(unlocked), "unlock_reason": unlocked,
        "contacts": ({"email": cand.contact_email, "phone": cand.phone, "telegram": cand.telegram,
                      "links": cand.links or {}} if unlocked else None),
    }
    return view
