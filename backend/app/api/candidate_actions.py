"""Кандидат: приглашения от работодателей, вакансии и отклики, регулярные задания, уведомления."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.deps import DB, Candidate, CurrentUser
from app.core.db import utcnow
from app.models import Application, Company, Complaint, Invitation, Notification, TaskAssignment, Vacancy
from app.schemas import ApplyIn, ComplaintIn, DeclineIn, Message, TaskSubmitIn
from app.services import interactions as ix
from app.services.candidates import own_view
from app.services.notify import audit, notify
from app.services.reference.taxonomy import DECLINE_REASONS, GRADE_NAMES, SPEC_NAMES
from app.services.resumes import category_brief, get_resume, graded_profiles

router = APIRouter(tags=["Кандидат: приглашения, вакансии, задания"])


# ------------------------------------------------------------------ приглашения

def _own_invitation(db, cand, inv_id: int) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if not inv or inv.candidate_id != cand.id:  # кандидат видит только свои приглашения
        raise HTTPException(404, "Приглашение не найдено")
    ix.expire_invitations(db, [inv])
    return inv


@router.get("/candidate/invitations", summary="Мои приглашения от работодателей")
def my_invitations(cand: Candidate, db: DB, status: str | None = None):
    q = select(Invitation).where(Invitation.candidate_id == cand.id).order_by(Invitation.created_at.desc())
    invs = list(db.scalars(q))
    ix.expire_invitations(db, invs)
    if status:
        invs = [i for i in invs if i.status == status]
    return [ix.invitation_for_candidate(i) for i in invs]


@router.get("/candidate/invitations/{inv_id}", summary="Открыть приглашение (статус → «просмотрено»)")
def open_invitation(inv_id: int, cand: Candidate, db: DB):
    inv = _own_invitation(db, cand, inv_id)
    if inv.status == "sent":
        inv.status = "viewed"
        inv.viewed_at = utcnow()
        db.commit()
    return ix.invitation_for_candidate(inv)


@router.post("/candidate/invitations/{inv_id}/accept", summary="Принять приглашение — контакты раскрываются",
             responses={409: {"model": Message}})
def accept_invitation(inv_id: int, cand: Candidate, db: DB):
    inv = _own_invitation(db, cand, inv_id)
    if inv.status not in ("sent", "viewed"):
        raise HTTPException(409, f"Нельзя принять приглашение в статусе «{ix.INVITATION_STATUSES[inv.status]}»")
    inv.status = "accepted"
    inv.viewed_at = inv.viewed_at or utcnow()
    inv.responded_at = utcnow()
    audit(db, cand.user_id, "contacts_unlocked", "candidate", cand.id, company_id=inv.company_id, invitation_id=inv.id)
    notify(db, inv.company.owner_user_id, "invitation_accepted", f"Кандидат {cand.public_id} принял приглашение",
           f"«{inv.title}»: контакты кандидата открыты в карточке.", f"/employer/candidates/{cand.id}", email=True)
    db.commit()
    ix.notify_ats(inv.company, "invitation.accepted",
                  {"invitation_id": inv.id, "title": inv.title, "candidate": own_view(cand)["contacts"]
                   | {"public_id": cand.public_id, "full_name": cand.full_name}})
    return ix.invitation_for_candidate(inv)


@router.post("/candidate/invitations/{inv_id}/decline", summary="Отклонить приглашение с причиной",
             responses={409: {"model": Message}})
def decline_invitation(inv_id: int, data: DeclineIn, cand: Candidate, db: DB):
    inv = _own_invitation(db, cand, inv_id)
    if inv.status not in ("sent", "viewed"):
        raise HTTPException(409, "Приглашение уже обработано")
    inv.status = "declined"
    inv.viewed_at = inv.viewed_at or utcnow()
    inv.responded_at = utcnow()
    inv.decline_reason, inv.decline_comment = data.reason, data.comment
    notify(db, inv.company.owner_user_id, "invitation_declined", f"Кандидат {cand.public_id} отклонил приглашение",
           f"Причина: {DECLINE_REASONS[data.reason]}" + (f". Комментарий: {data.comment}" if data.comment else ""),
           "/employer/invitations")
    db.commit()
    return ix.invitation_for_candidate(inv)


@router.post("/candidate/invitations/{inv_id}/complain", summary="Пожаловаться на приглашение (фиктивная вакансия и т. п.)",
             response_model=Message)
def complain(inv_id: int, data: ComplaintIn, cand: Candidate, db: DB):
    inv = _own_invitation(db, cand, inv_id)
    db.add(Complaint(reporter_user_id=cand.user_id, company_id=inv.company_id, invitation_id=inv.id, reason=data.reason,
                     comment=data.comment))
    comp = inv.company
    n = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.company_id == comp.id)) or 0
    comp.trust_score = round(max(0.0, comp.trust_score - 0.05 * (1 + n / 5)), 3)
    db.commit()
    return Message(detail="Жалоба принята. Работодатели с жалобами теряют индекс доверия и проходят проверку.")


# ------------------------------------------------------------------ вакансии и отклики

@router.get("/vacancies", summary="Опубликованные вакансии (с оценкой совпадения для кандидата)")
def vacancies(user: CurrentUser, db: DB, q: str | None = None, specialization: str | None = None,
              grade: str | None = None, work_format: str | None = None, salary_min: int | None = None,
              limit: int = Query(50, le=200)):
    stmt = select(Vacancy).join(Company).where(Vacancy.is_published.is_(True), Vacancy.status == "active")
    if specialization:
        stmt = stmt.where(Vacancy.specialization == specialization)
    if work_format:
        stmt = stmt.where(Vacancy.work_format == work_format)
    if salary_min:
        stmt = stmt.where(Vacancy.salary_to >= salary_min)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Vacancy.title.ilike(like), Vacancy.description.ilike(like), Company.name.ilike(like)))
    items = list(db.scalars(stmt.order_by(Vacancy.created_at.desc()).limit(limit)))
    if grade:
        items = [v for v in items if grade in (v.grades or [])]
    cand = user.candidate if user.role == "candidate" else None
    graded = bool(cand and graded_profiles(cand))  # категория хотя бы по одному резюме
    applied = set()
    if cand:
        applied = set(db.scalars(select(Application.vacancy_id).where(Application.candidate_id == cand.id,
                                                                       Application.status != "withdrawn")))
    out = []
    for v in items:
        row = ix.vacancy_brief(v) | {"company": ix.company_brief(v.company), "description": v.description[:400],
                                     "must_skills": v.must_skills, "nice_skills": v.nice_skills,
                                     "created_at": v.created_at, "applied": v.id in applied}
        if graded:
            sc = ix.pair_score(v, cand)
            row["match"] = sc["match"] if sc else None
            row["match_resume"] = sc and {"id": sc["resume_id"], "title": sc["resume_title"]}
        out.append(row)
    if graded:
        out.sort(key=lambda r: -(r.get("match") or 0))
    return out


@router.get("/vacancies/{vac_id}", summary="Вакансия")
def vacancy(vac_id: int, user: CurrentUser, db: DB):
    v = db.get(Vacancy, vac_id)
    if not v or not v.is_published:
        raise HTTPException(404, "Вакансия не найдена")
    out = ix.vacancy_brief(v) | {"company": ix.company_brief(v.company), "description": v.description,
                                 "team_description": v.team_description, "must_skills": v.must_skills,
                                 "nice_skills": v.nice_skills, "employment": v.employment, "created_at": v.created_at}
    if user.role == "candidate" and user.candidate and graded_profiles(user.candidate):
        sc = ix.pair_score(v, user.candidate)
        out["match"] = sc and {"match": sc["match"], "reasons": sc["reasons"], "components": sc["components"],
                               "resume_id": sc["resume_id"], "resume_title": sc["resume_title"]}
        out["resumes"] = [category_brief(p) for p in graded_profiles(user.candidate)]
        out["applied"] = bool(db.scalar(select(Application.id).where(Application.candidate_id == user.candidate.id,
                                                                     Application.vacancy_id == v.id,
                                                                     Application.status != "withdrawn")))
    return out


@router.post("/vacancies/{vac_id}/apply", summary="Откликнуться на вакансию", responses={409: {"model": Message}})
def apply(vac_id: int, data: ApplyIn, cand: Candidate, db: DB):
    v = db.get(Vacancy, vac_id)
    if not v or not v.is_published or v.status != "active":
        raise HTTPException(404, "Вакансия не найдена или закрыта")
    if not cand.consent_pd:
        raise HTTPException(409, "Нужно согласие на обработку персональных данных")
    exists = db.scalar(select(Application).where(Application.candidate_id == cand.id, Application.vacancy_id == v.id,
                                                 Application.status != "withdrawn"))
    if exists:
        raise HTTPException(409, "Вы уже откликнулись на эту вакансию")
    if data.resume_id:
        get_resume(cand, data.resume_id)  # 404, если резюме чужое
    sc = ix.pair_score(v, cand, data.resume_id)
    rid = data.resume_id if data.resume_id is not None else (sc["resume_id"] if sc else 0)
    prof = ix.profile_by_resume(cand, rid)
    a = Application(candidate_id=cand.id, vacancy_id=v.id, resume_id=rid or None, cover_letter=data.cover_letter,
                    match_score=sc["score"] if sc else None)
    db.add(a)
    notify(db, v.company.owner_user_id, "application_new", f"Новый отклик на «{v.title}»",
           f"Кандидат {cand.public_id}" + (f", категория {SPEC_NAMES.get(prof.grade_specialization, '')} · "
                                          f"{GRADE_NAMES[prof.grade]}" if prof.grade else ", без категории"),
           f"/employer/vacancies/{v.id}")
    db.commit()
    # Отклик — инициатива кандидата: контакты открываются компании, поэтому их можно передать в ATS
    contacts = own_view(cand)["contacts"] | {"public_id": cand.public_id, "full_name": cand.full_name}
    ix.notify_ats(v.company, "application.created",
                  {"application_id": a.id, "vacancy_id": v.id, "vacancy_title": v.title, "candidate": contacts})
    return ix.application_for_candidate(a)


@router.get("/candidate/applications", summary="Мои отклики и их статусы")
def my_applications(cand: Candidate, db: DB):
    apps = db.scalars(select(Application).where(Application.candidate_id == cand.id).order_by(Application.created_at.desc()))
    return [ix.application_for_candidate(a) for a in apps]


@router.post("/candidate/applications/{app_id}/withdraw", summary="Отозвать отклик")
def withdraw_application(app_id: int, cand: Candidate, db: DB):
    a = db.get(Application, app_id)
    if not a or a.candidate_id != cand.id:
        raise HTTPException(404, "Отклик не найден")
    a.status = "withdrawn"
    db.commit()
    return ix.application_for_candidate(a)


# ------------------------------------------------------------------ регулярные задания

@router.get("/candidate/tasks", summary="Регулярные задания от работодателей (система периодически предлагает новые)")
def my_tasks(cand: Candidate, db: DB):
    ix.offer_tasks(db, cand)
    rows = db.scalars(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)
                      .order_by(TaskAssignment.offered_at.desc()))
    return [ix.task_view(t) for t in rows]


def _own_task(db, cand, ta_id: int) -> TaskAssignment:
    ta = db.get(TaskAssignment, ta_id)
    if not ta or ta.candidate_id != cand.id:
        raise HTTPException(404, "Задание не найдено")
    return ta


@router.post("/candidate/tasks/{ta_id}/submit", summary="Отправить решение или подход", responses={409: {"model": Message}})
def submit_task(ta_id: int, data: TaskSubmitIn, cand: Candidate, db: DB):
    ta = _own_task(db, cand, ta_id)
    if ta.status not in ("offered",):
        raise HTTPException(409, "Задание уже отправлено")
    ta.answer = data.answer
    ta.status = "submitted"
    ta.submitted_at = utcnow()
    ta.auto_score = ix.auto_score(ta.task, data.answer)
    notify(db, ta.task.company.owner_user_id, "task_submitted", f"Решение задания «{ta.task.title}»",
           f"Кандидат {cand.public_id} отправил ответ", "/employer/tasks")
    db.commit()
    return ix.task_view(ta)


@router.post("/candidate/tasks/{ta_id}/skip", summary="Пропустить задание")
def skip_task(ta_id: int, cand: Candidate, db: DB):
    ta = _own_task(db, cand, ta_id)
    if ta.status == "offered":
        ta.status = "skipped"
        db.commit()
    return ix.task_view(ta)


# ------------------------------------------------------------------ уведомления (обе роли)

@router.get("/notifications", tags=["Уведомления"], summary="Мои уведомления")
def notifications(user: CurrentUser, db: DB, limit: int = Query(30, le=100)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc()).limit(limit))
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id,
                                                                            Notification.is_read.is_(False))) or 0
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                                         "is_read": n.is_read, "created_at": n.created_at} for n in rows]}


@router.post("/notifications/read", tags=["Уведомления"], summary="Отметить все уведомления прочитанными",
             response_model=Message)
def read_all(user: CurrentUser, db: DB):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).update(
        {Notification.is_read: True})
    db.commit()
    return Message(detail="ok")
