"""Общая логика приглашений, откликов и регулярных заданий (используется роутерами обеих ролей)."""
from __future__ import annotations

import logging
import random
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import utcnow
from app.models import Application, CandidateProfile, Company, Invitation, Task, TaskAssignment, Vacancy
from app.services.matching.profile import recompute_candidate
from app.services.matching.ranking import Need, score_candidates
from app.services.reference.taxonomy import DECLINE_REASONS, GRADE_NAMES, SPEC_NAMES, WORK_FORMATS
from app.services.resumes import ResumeView, category_brief, graded_profiles
from app.services.sandbox.tasks import public_results, task_payload

log = logging.getLogger("interactions")

INVITATION_STATUSES = {"sent": "Отправлено", "viewed": "Просмотрено", "accepted": "Принято", "declined": "Отклонено",
                       "withdrawn": "Отозвано", "expired": "Истекло"}
APPLICATION_STATUSES = {"sent": "Отправлен", "viewed": "Просмотрен", "accepted": "Приглашение на интервью",
                        "rejected": "Отказ", "withdrawn": "Отозван"}


def need_from_vacancy(v: Vacancy) -> Need:
    return Need(specialization=v.specialization, grades=v.grades or ["middle"], must_skills=v.must_skills or [],
                nice_skills=v.nice_skills or [], salary_from=v.salary_from, salary_to=v.salary_to,
                work_format=v.work_format, city=v.city, text=f"{v.description}\n{v.team_description or ''}",
                title=v.title, require_fsp=v.require_fsp)


def pair_score(v: Vacancy, cand: CandidateProfile, resume_id: int | None = None) -> dict | None:
    """Соответствие кандидата вакансии по лучшему из его резюме с категорией (или по указанному резюме)."""
    graded = [p for p in graded_profiles(cand) if resume_id is None or (p.resume_id or 0) == resume_id]
    if not graded:
        return None
    return max(score_candidates(need_from_vacancy(v), graded), key=lambda r: r["score"])


def profile_by_resume(cand: CandidateProfile, resume_id: int | None):
    """Резюме, к которому относится приглашение/отклик; удалённое резюме — показываем основной профиль."""
    if resume_id:
        res = next((r for r in cand.resumes if r.id == resume_id), None)
        if res is not None:
            return ResumeView(cand, res)
    return cand


def invitation_profile(inv: Invitation):
    return profile_by_resume(inv.candidate, inv.resume_id)


def application_profile(a: Application):
    return profile_by_resume(a.candidate, a.resume_id)


def expire_invitations(db: Session, invitations: list[Invitation]) -> None:
    now = utcnow()
    changed = False
    for inv in invitations:
        if inv.status in ("sent", "viewed") and inv.expires_at and inv.expires_at < now:
            inv.status = "expired"
            changed = True
    if changed:
        db.commit()


def company_brief(c: Company) -> dict:
    return {"id": c.id, "name": c.name, "industry": c.industry, "city": c.city, "website": c.website,
            "description": c.description, "size": c.size, "trust_score": round(c.trust_score, 2),
            "domain_verified": c.domain_verified}


def vacancy_brief(v: Vacancy | None) -> dict | None:
    if v is None:
        return None
    return {"id": v.id, "title": v.title, "specialization": v.specialization,
            "specialization_name": SPEC_NAMES.get(v.specialization), "grades": v.grades,
            "grade_names": [GRADE_NAMES[g] for g in v.grades or []], "salary_from": v.salary_from,
            "salary_to": v.salary_to, "work_format": v.work_format, "work_format_name": WORK_FORMATS.get(v.work_format),
            "city": v.city, "is_published": v.is_published, "status": v.status}


def invitation_for_candidate(inv: Invitation) -> dict:
    accepted = inv.status == "accepted"
    c = inv.company
    return {
        "id": inv.id, "status": inv.status, "status_name": INVITATION_STATUSES[inv.status], "title": inv.title,
        "message": inv.message, "salary_from": inv.salary_from, "salary_to": inv.salary_to,
        "work_format": inv.work_format, "work_format_name": WORK_FORMATS.get(inv.work_format or ""),
        "company": company_brief(c), "vacancy": vacancy_brief(inv.vacancy),
        "contact_method": inv.contact_method,
        "company_contacts": {"name": c.contact_name, "email": c.contact_email, "phone": c.contact_phone,
                             "telegram": c.contact_telegram} if accepted else None,
        "why_you": [r for r in (inv.match_snapshot or {}).get("reasons", []) if r["kind"] == "plus"][:4],
        "match": inv.match_score and round(inv.match_score * 100),
        "decline_reason": inv.decline_reason, "decline_reason_name": DECLINE_REASONS.get(inv.decline_reason or ""),
        "decline_comment": inv.decline_comment,
        "created_at": inv.created_at, "viewed_at": inv.viewed_at, "responded_at": inv.responded_at,
        "expires_at": inv.expires_at,
        "resume": category_brief(invitation_profile(inv)),  # по какому резюме (категории) пришло приглашение
    }


def application_for_candidate(a: Application) -> dict:
    return {"id": a.id, "status": a.status, "status_name": APPLICATION_STATUSES[a.status],
            "vacancy": vacancy_brief(a.vacancy), "company": company_brief(a.vacancy.company),
            "cover_letter": a.cover_letter, "employer_comment": a.employer_comment, "match_score": a.match_score,
            "created_at": a.created_at, "updated_at": a.updated_at, "viewed_at": a.viewed_at,
            "resume": category_brief(application_profile(a))}


def notify_ats(company: Company, event: str, payload: dict) -> None:
    """Задел интеграции с ATS: webhook при принятии приглашения / отклике (best effort, без ретраев в MVP)."""
    if not company.ats_webhook_url:
        return
    try:
        httpx.post(company.ats_webhook_url, json={"event": event, **payload}, timeout=3.0)
    except httpx.HTTPError as exc:
        log.warning("ATS webhook %s недоступен: %s", company.ats_webhook_url, exc)


# ------------------------------------------------------------------ регулярные задания

def offer_tasks(db: Session, cand: CandidateProfile) -> TaskAssignment | None:
    """Раз в N дней предлагает кандидату с присвоенной категорией короткое задание работодателя его профиля
    (по любой из категорий его резюме)."""
    cats = {(p.grade_specialization, p.grade) for p in graded_profiles(cand)}
    if not cats or not cand.open_to_offers:
        return None
    last = db.scalar(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)
                     .order_by(TaskAssignment.offered_at.desc()))
    if last and last.offered_at > utcnow() - timedelta(days=settings.task_offer_interval_days):
        return None
    seen = set(db.scalars(select(TaskAssignment.task_id).where(TaskAssignment.candidate_id == cand.id)))
    specs = {s for s, _ in cats}
    tasks = [t for t in db.scalars(select(Task).where(Task.is_active.is_(True), Task.specialization.in_(specs)))
             if t.id not in seen and (not t.grades or any((t.specialization, g) in cats for g in t.grades))]
    if not tasks:
        return None
    task = random.choice(tasks)
    ta = TaskAssignment(task_id=task.id, candidate_id=cand.id, due_at=utcnow() + timedelta(days=7))
    db.add(ta)
    db.commit()
    return ta


def auto_score(task: Task, answer: str) -> float | None:
    """Предварительная автооценка по эталону/рубрике: TF-IDF-близость ответа к ожидаемому решению."""
    if not task.expected_answer:
        return None
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    m = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform([task.expected_answer, answer])
    return round(float(min(1.0, cosine_similarity(m[0:1], m[1:2])[0, 0] / 0.6)), 3)


def apply_task_review(db: Session, ta: TaskAssignment) -> None:
    cand = ta.candidate
    reviewed = list(db.scalars(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id,
                                                            TaskAssignment.status == "reviewed")))
    scores = [(t.score - 1) / 4 for t in reviewed if t.score]
    cand.tasks_done = len(reviewed)
    cand.tasks_score = round(sum(scores) / len(scores), 3) if scores else 0.0
    cand.last_task_at = max((t.reviewed_at for t in reviewed if t.reviewed_at), default=utcnow())
    recompute_candidate(db, cand)


def task_view(ta: TaskAssignment, for_employer: bool = False) -> dict:
    t = ta.task
    out = {"id": ta.id, "status": ta.status, "answer": ta.answer, "score": ta.score, "feedback": ta.feedback,
           "auto_score": ta.auto_score if for_employer else None, "offered_at": ta.offered_at, "due_at": ta.due_at,
           "submitted_at": ta.submitted_at, "reviewed_at": ta.reviewed_at,
           "task": {"id": t.id, "title": t.title, "description": t.description, "kind": t.kind,
                    "time_estimate_min": t.time_estimate_min, "company": t.company.name,
                    "specialization_name": SPEC_NAMES.get(t.specialization), **task_payload(t)}}
    if t.kind == "code":
        out["code"] = ta.code
        out["results"] = public_results(ta.run_results, for_employer)
        out["runs_count"] = ta.runs_count or 0
        if for_employer:
            out["plagiarism"], out["signals"] = ta.plagiarism, ta.signals
    if for_employer:
        cand = ta.candidate
        out["candidate"] = {"id": cand.id, "public_id": cand.public_id, "grade": cand.grade,
                            "grade_name": GRADE_NAMES.get(cand.grade or ""),
                            "specialization_name": SPEC_NAMES.get(cand.grade_specialization or "")}
    return out
