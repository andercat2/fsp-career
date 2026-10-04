"""Зависимости FastAPI: текущий пользователь из JWT и разграничение доступа по ролям."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, utcnow
from app.core.security import decode_access_token
from app.models import CandidateProfile, Company, User

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/token", auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, token: Annotated[str | None, Depends(oauth2)]) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный или просроченный токен",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден или заблокирован")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Подтвердите адрес электронной почты")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_candidate(db: DB, user: CurrentUser) -> CandidateProfile:
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только кандидатам")
    cand = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if cand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль кандидата не найден")
    if (utcnow() - cand.last_active_at).total_seconds() > 3600:
        cand.last_active_at = utcnow()
        db.commit()
    return cand


def get_company(db: DB, user: CurrentUser) -> Company:
    if user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только работодателям")
    comp = db.scalar(select(Company).where(Company.owner_user_id == user.id))
    if comp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль компании не найден")
    return comp


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только администратору")
    return user


Candidate = Annotated[CandidateProfile, Depends(get_candidate)]
EmployerCompany = Annotated[Company, Depends(get_company)]
Admin = Annotated[User, Depends(require_admin)]
