"""Личный кабинет кандидата: профиль, резюме (PDF с автораспознаванием), PDF-профиль, приватность, согласия."""
from datetime import timedelta

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select

from app.api.deps import DB, Candidate
from app.core.db import utcnow
from app.models import (
    Application,
    AuditLog,
    Consent,
    Invitation,
    Notification,
    SurveyResponse,
    TaskAssignment,
    TestSession,
    User,
)
from app.schemas import CandidateProfileIn, ConsentIn, Message, PrivacyIn
from app.services.candidates import own_view
from app.services.matching.profile import profile_completeness, recompute_candidate
from app.services.nlp.resume_parser import parse_resume_pdf
from app.services.notify import audit
from app.services.pdf.profile_pdf import render_profile_pdf
from app.services.reference.skills import SKILL_BY_ID

router = APIRouter(prefix="/candidate", tags=["Кандидат: профиль"])

MAX_PDF = 5 * 1024 * 1024


@router.get("/profile", summary="Мой профиль")
def get_profile(cand: Candidate):
    return own_view(cand)


@router.put("/profile", summary="Сохранить профиль (ручное заполнение или подтверждение распознанного резюме)")
def put_profile(data: CandidateProfileIn, cand: Candidate, db: DB):
    payload = data.model_dump()
    payload["skills"] = [s for s in dict.fromkeys(payload["skills"]) if s in SKILL_BY_ID]
    payload["experience"] = [e for e in payload["experience"] if any(e.values())]
    payload["education"] = [e for e in payload["education"] if e.get("title")]
    payload["languages"] = [x for x in payload["languages"] if x.get("name")]
    for k, v in payload.items():
        setattr(cand, k, v)
    recompute_candidate(db, cand)
    db.commit()
    return own_view(cand)


@router.post("/resume", summary="Загрузить PDF-резюме и распознать поля",
             description="Возвращает распознанные поля для проверки; профиль не меняется, пока кандидат не сохранит его.",
             responses={400: {"model": Message}, 413: {"model": Message}})
async def upload_resume(cand: Candidate, db: DB, file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_PDF:
        raise HTTPException(413, "Файл больше 5 МБ")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Ожидается файл в формате PDF")
    try:
        text, parsed = parse_resume_pdf(data)
    except Exception as exc:  # noqa: BLE001 — повреждённый PDF не должен давать 500
        raise HTTPException(400, f"Не удалось прочитать PDF: {exc}") from exc
    if len(text.strip()) < 30:
        raise HTTPException(400, "В PDF не найден текст (возможно, это скан). Заполните профиль вручную.")
    cand.resume_text = text[:50000]
    cand.resume_filename = (file.filename or "resume.pdf")[:255]
    db.commit()
    parsed["skills_detail"] = [{"id": s, "name": SKILL_BY_ID[s].name} for s in parsed["skills"] if s in SKILL_BY_ID]
    return parsed


@router.get("/profile/pdf", summary="Стандартизированный PDF-профиль",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def profile_pdf(cand: Candidate):
    pdf = render_profile_pdf(own_view(cand))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="profile-{cand.public_id}.pdf"'})


@router.put("/privacy", summary="Настройки приватности: что видит работодатель")
def put_privacy(data: PrivacyIn, cand: Candidate, db: DB):
    cand.privacy = data.model_dump()
    db.commit()
    return cand.privacy


@router.post("/consents", summary="Дать или отозвать согласие (152-ФЗ)")
def consents(data: ConsentIn, cand: Candidate, db: DB, request: Request):
    db.add(Consent(user_id=cand.user_id, kind=data.kind, granted=data.granted,
                   ip=request.client.host if request.client else None,
                   user_agent=request.headers.get("user-agent", "")[:255]))
    if data.kind == "pd_processing":
        cand.consent_pd = data.granted
        if not data.granted:
            cand.consent_publish = False
    else:
        if data.granted and not cand.consent_pd:
            raise HTTPException(409, "Сначала дайте согласие на обработку персональных данных")
        cand.consent_publish = data.granted
    db.commit()
    return {"consent_pd": cand.consent_pd, "consent_publish": cand.consent_publish}


@router.get("/consents", summary="Журнал согласий")
def consent_log(cand: Candidate, db: DB):
    rows = db.scalars(select(Consent).where(Consent.user_id == cand.user_id).order_by(Consent.created_at.desc()))
    return [{"kind": c.kind, "granted": c.granted, "version": c.version, "created_at": c.created_at} for c in rows]


@router.get("/dashboard", summary="Сводка для главной страницы кандидата")
def dashboard(cand: Candidate, db: DB):
    since = utcnow() - timedelta(days=30)
    views = db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == "view_candidate", AuditLog.entity_id == str(cand.id), AuditLog.created_at >= since)) or 0
    inv_new = db.scalar(select(func.count()).select_from(Invitation).where(
        Invitation.candidate_id == cand.id, Invitation.status == "sent")) or 0
    inv_total = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.candidate_id == cand.id)) or 0
    apps = db.scalar(select(func.count()).select_from(Application).where(Application.candidate_id == cand.id)) or 0
    tasks_open = db.scalar(select(func.count()).select_from(TaskAssignment).where(
        TaskAssignment.candidate_id == cand.id, TaskAssignment.status == "offered")) or 0
    tests = db.scalar(select(func.count()).select_from(TestSession).where(
        TestSession.candidate_id == cand.id, TestSession.status == "completed")) or 0
    completeness = profile_completeness(cand)
    steps = [
        {"key": "consent", "title": "Согласие на публикацию профиля", "done": cand.consent_publish,
         "link": "/candidate/settings", "required": True},
        {"key": "profile", "title": "Заполнить профиль или загрузить резюме", "done": completeness >= 0.6,
         "link": "/candidate/profile", "required": True, "progress": round(completeness, 2)},
        {"key": "survey", "title": "Пройти опрос по отрасли и специализации", "done": bool(cand.survey_completed_at),
         "link": "/candidate/testing", "required": True},
        {"key": "test", "title": "Пройти тест на заявленный грейд", "done": bool(cand.grade),
         "link": "/candidate/testing", "required": True},
        {"key": "fsp", "title": "Привязать ФСП ID (необязательно)", "done": bool(cand.fsp_id),
         "link": "/candidate/settings", "required": False},
    ]
    visible = bool(cand.grade and cand.consent_publish and (cand.privacy or {}).get("visible_in_search", True))
    return {
        "profile": own_view(cand), "steps": steps, "visible_to_employers": visible,
        "stats": {"profile_views_30d": views, "invitations_new": inv_new, "invitations_total": inv_total,
                  "applications": apps, "tasks_open": tasks_open, "tests_completed": tests},
    }


@router.get("/export", summary="Выгрузка всех моих данных (152-ФЗ)")
def export(cand: Candidate, db: DB):
    def rows(model, col):
        return [{c.name: getattr(r, c.name) for c in model.__table__.columns}
                for r in db.scalars(select(model).where(col == cand.id))]

    return {
        "profile": own_view(cand),
        "surveys": rows(SurveyResponse, SurveyResponse.candidate_id),
        "tests": [{k: v for k, v in t.items() if k != "seed"} for t in rows(TestSession, TestSession.candidate_id)],
        "invitations": rows(Invitation, Invitation.candidate_id),
        "applications": rows(Application, Application.candidate_id),
        "tasks": rows(TaskAssignment, TaskAssignment.candidate_id),
        "consents": consent_log(cand, db),
    }


@router.delete("/account", summary="Удалить аккаунт и персональные данные", response_model=Message)
def delete_account(cand: Candidate, db: DB):
    user = db.get(User, cand.user_id)
    audit(db, None, "account_deleted", "candidate", cand.id)
    db.query(Notification).filter(Notification.user_id == user.id).delete()
    db.delete(cand)
    db.delete(user)
    db.commit()
    return Message(detail="Аккаунт и персональные данные удалены")
