"""Связь профиля с ФСП ID (OIDC, совместимо с Keycloak) и вход через ФСП ID."""
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import DB, Candidate
from app.core.config import settings
from app.core.db import utcnow
from app.core.security import create_access_token
from app.models import CandidateProfile, Consent, OAuthState, User
from app.schemas import Message
from app.services.candidates import new_public_id
from app.services.fsp import client
from app.services.fsp.scoring import fsp_summary
from app.services.matching.profile import recompute_candidate
from app.services.notify import audit

router = APIRouter(prefix="/fsp", tags=["Интеграция с ФСП"])
STATE_TTL = timedelta(minutes=10)


def _start(db, purpose: str, user_id: int | None) -> str:
    if not settings.fsp_enabled:
        raise HTTPException(503, "Интеграция с ФСП ID отключена")
    verifier, challenge = client.pkce_pair()
    st = OAuthState(state=secrets.token_urlsafe(24), user_id=user_id, purpose=purpose, nonce=secrets.token_urlsafe(16),
                    code_verifier=verifier)
    db.add(st)
    db.commit()
    return client.authorize_url(st.state, st.nonce, challenge)


@router.get("/link", summary="Начать привязку ФСП ID (возвращает URL авторизации ФСП)")
def link_start(cand: Candidate, db: DB):
    return {"authorize_url": _start(db, "link", cand.user_id)}


@router.get("/login", summary="Начать вход через ФСП ID")
def login_start(db: DB):
    return {"authorize_url": _start(db, "login", None)}


def _front(path: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}{path}", status_code=302)


def _apply_participant(db, cand: CandidateProfile, fsp_id: str, participant: dict | None) -> None:
    cand.fsp_id = fsp_id
    cand.fsp_linked_at = cand.fsp_linked_at or utcnow()
    cand.fsp_synced_at = utcnow()
    # Участник без истории — корректный случай: профиль привязан, достижений нет.
    cand.fsp_profile = participant or {"fsp_id": fsp_id, "achievements": []}
    recompute_candidate(db, cand)


@router.get("/callback", include_in_schema=True, summary="Redirect URI для OIDC-провайдера ФСП ID")
def callback(db: DB, state: str, code: str | None = None, error: str | None = None):
    st = db.get(OAuthState, state)
    if not st or st.created_at < utcnow() - STATE_TTL:
        return _front("/login?fsp_error=" + quote("Сессия авторизации ФСП истекла, попробуйте ещё раз"))
    db.delete(st)
    db.commit()
    back = "/candidate/settings" if st.purpose == "link" else "/login"
    if error or not code:
        return _front(f"{back}?fsp_error=" + quote(error or "Авторизация отменена"))
    try:
        tokens = client.exchange_code(code, st.code_verifier)
        claims = client.verify_id_token(tokens["id_token"], st.nonce)
        fsp_id = client.fsp_id_from_claims(claims)
        participant = client.fetch_participant(fsp_id, tokens.get("access_token"))
    except client.FspError as exc:
        return _front(f"{back}?fsp_error=" + quote(str(exc)))

    owner = db.scalar(select(CandidateProfile).where(CandidateProfile.fsp_id == fsp_id))
    if st.purpose == "link":
        cand = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == st.user_id))
        if owner and owner.id != cand.id:
            return _front(f"{back}?fsp_error=" + quote("Этот ФСП ID уже привязан к другому профилю"))
        _apply_participant(db, cand, fsp_id, participant)
        audit(db, cand.user_id, "fsp_linked", "candidate", cand.id, fsp_id=fsp_id)
        db.commit()
        return _front(f"{back}?fsp=linked")

    # Вход через ФСП ID: существующий профиль или новый кандидат с подтверждённым у провайдера e-mail
    if owner is None:
        email = (claims.get("email") or f"{fsp_id.lower()}@fsp-id.local").lower()
        user = db.scalar(select(User).where(User.email == email))
        if user and user.role != "candidate":
            return _front("/login?fsp_error=" + quote("E-mail из ФСП ID занят учётной записью работодателя"))
        if user is None:
            user = User(email=email, password_hash=None, role="candidate", email_verified=True)
            db.add(user)
            db.flush()
            db.add(Consent(user_id=user.id, kind="pd_processing", granted=True, user_agent="fsp-id-login"))
            owner = CandidateProfile(user_id=user.id, public_id=new_public_id(db), contact_email=email, consent_pd=True,
                                     full_name=claims.get("name"))
            db.add(owner)
            db.flush()
        else:
            owner = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        _apply_participant(db, owner, fsp_id, participant)
    user = db.get(User, owner.user_id)
    user.last_login_at = utcnow()
    db.commit()
    token = create_access_token(user.id, user.role)
    return _front(f"/auth/fsp#token={token}")


@router.post("/sync", summary="Обновить достижения из реестра ФСП", responses={409: {"model": Message}})
def sync(cand: Candidate, db: DB):
    if not cand.fsp_id:
        raise HTTPException(409, "ФСП ID не привязан")
    try:
        participant = client.fetch_participant(cand.fsp_id)
    except client.FspError as exc:
        raise HTTPException(503, str(exc)) from exc
    _apply_participant(db, cand, cand.fsp_id, participant)
    db.commit()
    return fsp_summary(cand.fsp_profile, cand.grade_specialization or cand.specialization)


@router.delete("/link", summary="Отвязать ФСП ID", response_model=Message)
def unlink(cand: Candidate, db: DB):
    audit(db, cand.user_id, "fsp_unlinked", "candidate", cand.id, fsp_id=cand.fsp_id)
    cand.fsp_id = None
    cand.fsp_profile = None
    cand.fsp_linked_at = None
    cand.fsp_synced_at = None
    recompute_candidate(db, cand)
    db.commit()
    return Message(detail="ФСП ID отвязан, данные о достижениях удалены из профиля")
