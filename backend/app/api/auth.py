"""Регистрация по e-mail с подтверждением адреса, вход, выдача JWT, гостевой демо-доступ кандидата."""
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.db import utcnow
from app.core.email import send_email
from app.core.security import (
    create_access_token,
    generate_code,
    hash_code,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models import CandidateProfile, Company, Consent, EmailCode, Notification, SurveyResponse, User
from app.schemas import GuestIn, LoginIn, Message, RegisterIn, RegisterOut, ResendIn, TokenOut, UserOut, VerifyIn
from app.services.candidates import new_public_id
from app.services.reference.taxonomy import SPEC_BY_CODE, SPEC_NAMES

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

CODE_TTL_MIN = 30
MAX_CODE_ATTEMPTS = 5
GUEST_DOMAIN = "guest.example"  # зарезервированный домен: на такие адреса письма не уходят
GUEST_TTL_DAYS = 2
GUEST_PER_IP_HOUR = 20
_login_attempts: dict[str, deque] = defaultdict(deque)


def _throttle(key: str, limit: int = 8, window: int = 300) -> None:
    q = _login_attempts[key]
    now = time.monotonic()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много попыток, повторите через несколько минут")
    q.append(now)


def _issue_code(db, user: User) -> str:
    code = generate_code()
    db.add(EmailCode(user_id=user.id, code_hash=hash_code(code), expires_at=utcnow() + timedelta(minutes=CODE_TTL_MIN)))
    send_email(user.email, "Код подтверждения — ФСП Карьера",
               f"Ваш код подтверждения: {code}\nКод действует {CODE_TTL_MIN} минут.")
    return code


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


def is_guest(user: User) -> bool:
    return user.email.endswith("@" + GUEST_DOMAIN)


def _purge_guests(db) -> int:
    """Гостевые аккаунты живут GUEST_TTL_DAYS дня: затем удаляются вместе с данными (как при удалении аккаунта)."""
    old = list(db.scalars(select(User).where(User.email.like(f"guest-%@{GUEST_DOMAIN}"),
                                             User.created_at < utcnow() - timedelta(days=GUEST_TTL_DAYS))))
    for u in old:
        db.query(Notification).filter(Notification.user_id == u.id).delete()
        if u.candidate is not None:
            db.delete(u.candidate)
        db.delete(u)
    return len(old)


@router.post("/guest", response_model=TokenOut, status_code=201,
             responses={403: {"model": Message}, 422: {"model": Message}, 429: {"model": Message}},
             summary="Попробовать как кандидат: демо-аккаунт без регистрации")
def guest(data: GuestIn, db: DB, request: Request):
    """Одноразовый аккаунт кандидата в один клик — чтобы сразу пройти тест (в том числе членам жюри): опрос
    заполняется из запроса, профиль не публикуется работодателям, через 2 дня аккаунт удаляется. На один адрес —
    не больше 20 аккаунтов в час; в продуктиве режим отключается переменной GUEST_MODE=false."""
    if not settings.guest_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Демо-доступ без регистрации отключён")
    spec = SPEC_BY_CODE.get(data.specialization)
    if spec is None:
        raise HTTPException(422, "Неизвестная специализация")
    if data.language not in spec["languages"]:
        raise HTTPException(422, "Этот язык не относится к выбранной специализации")
    _throttle(f"guest:{request.client.host if request.client else '-'}", limit=GUEST_PER_IP_HOUR, window=3600)
    _purge_guests(db)
    email = f"guest-{secrets.token_hex(5)}@{GUEST_DOMAIN}"
    user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(24)), role="candidate",
                email_verified=True, is_demo=True)
    db.add(user)
    db.flush()
    now = utcnow()
    cand = CandidateProfile(user_id=user.id, public_id=new_public_id(db), contact_email=email, consent_pd=True,
                            consent_publish=False, headline=f"{SPEC_NAMES[data.specialization]} (демо)",
                            specialization=data.specialization, primary_language=data.language,
                            claimed_grade=data.claimed_grade, industries=[], survey_completed_at=now)
    db.add(cand)
    db.flush()
    db.add(Consent(user_id=user.id, kind="pd_processing", granted=True,
                   ip=request.client.host if request.client else None,
                   user_agent=request.headers.get("user-agent", "")[:255]))
    db.add(SurveyResponse(candidate_id=cand.id, specialization=data.specialization, claimed_grade=data.claimed_grade,
                          warnings=[], answers={"specialization": data.specialization, "language": data.language,
                                                "claimed_grade": data.claimed_grade, "guest": True}))
    db.commit()
    return _token(user)


@router.post("/register", response_model=RegisterOut, status_code=201,
             responses={409: {"model": Message, "description": "E-mail уже зарегистрирован"}},
             summary="Регистрация кандидата или работодателя")
def register(data: RegisterIn, db: DB, request: Request):
    email = data.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user and user.email_verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким e-mail уже зарегистрирован")
    if user is None:
        user = User(email=email, password_hash=hash_password(data.password), role=data.role)
        db.add(user)
        db.flush()
        if data.role == "candidate":
            db.add(CandidateProfile(user_id=user.id, public_id=new_public_id(db), contact_email=email, consent_pd=True))
        else:
            db.add(Company(owner_user_id=user.id, name=data.company_name or "Новая компания", contact_email=email))
        db.add(Consent(user_id=user.id, kind="pd_processing", granted=True,
                       ip=request.client.host if request.client else None,
                       user_agent=request.headers.get("user-agent", "")[:255]))
    else:
        user.password_hash = hash_password(data.password)
    code = _issue_code(db, user)
    db.commit()
    return RegisterOut(detail="Код подтверждения отправлен на e-mail", email=email,
                       dev_code=code if settings.email_dev_mode else None)


@router.post("/verify-email", response_model=TokenOut, summary="Подтверждение e-mail кодом",
             responses={400: {"model": Message}, 404: {"model": Message}, 429: {"model": Message}})
def verify_email(data: VerifyIn, db: DB):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if user.email_verified:
        return _token(user)
    code = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.used_at.is_(None))
                     .order_by(EmailCode.created_at.desc()))
    if not code or code.expires_at < utcnow():
        raise HTTPException(400, "Код истёк — запросите новый")
    if code.attempts >= MAX_CODE_ATTEMPTS:
        raise HTTPException(429, "Превышено число попыток — запросите новый код")
    if code.code_hash != hash_code(data.code):
        code.attempts += 1
        db.commit()
        raise HTTPException(400, "Неверный код")
    code.used_at = utcnow()
    user.email_verified = True
    user.last_login_at = utcnow()
    db.commit()
    return _token(user)


@router.post("/resend-code", response_model=RegisterOut, summary="Повторная отправка кода")
def resend(data: ResendIn, db: DB):
    _throttle("resend:" + data.email.lower(), limit=3, window=120)
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or user.email_verified:
        return RegisterOut(detail="Если адрес зарегистрирован и не подтверждён, код отправлен", email=data.email)
    code = _issue_code(db, user)
    db.commit()
    return RegisterOut(detail="Код отправлен повторно", email=data.email,
                       dev_code=code if settings.email_dev_mode else None)


def _login(db, email: str, password: str) -> TokenOut:
    _throttle("login:" + email.lower())
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный e-mail или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись заблокирована")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "E-mail не подтверждён")
    user.last_login_at = utcnow()
    if needs_rehash(user.password_hash):  # хеш с прежними параметрами Argon2 — пересчитываем при входе
        user.password_hash = hash_password(password)
    db.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut, summary="Вход по e-mail и паролю",
             responses={401: {"model": Message}, 403: {"model": Message}, 429: {"model": Message}})
def login(data: LoginIn, db: DB):
    return _login(db, data.email, data.password)


@router.post("/token", response_model=TokenOut, summary="OAuth2 password flow (для кнопки Authorize в Swagger)")
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    return _login(db, form.username, form.password)


@router.get("/me", summary="Текущий пользователь")
def me(user: CurrentUser, db: DB):
    out = UserOut.model_validate(user).model_dump() | {"guest": is_guest(user)}
    if user.role == "candidate":
        cand = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        out["candidate"] = {"id": cand.id, "public_id": cand.public_id, "full_name": cand.full_name,
                            "grade": cand.grade, "specialization": cand.specialization} if cand else None
    elif user.role == "employer":
        comp = db.scalar(select(Company).where(Company.owner_user_id == user.id))
        out["company"] = {"id": comp.id, "name": comp.name} if comp else None
    return out
