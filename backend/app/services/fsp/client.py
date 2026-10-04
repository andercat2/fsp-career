"""Интеграция с ФСП ID и реестром достижений.

ФСП ID — OpenID Connect провайдер. Пути эндпоинтов совпадают с Keycloak
(`/realms/<realm>/protocol/openid-connect/{auth,token,certs,userinfo}`), поэтому для перехода на реальный
Keycloak ФСП достаточно поменять FSP_OIDC_ISSUER и учётные данные клиента. Поток: authorization code + PKCE,
id_token проверяется по JWKS (RS256), nonce защищает от повтора.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings

_TIMEOUT = httpx.Timeout(5.0)


class FspError(RuntimeError):
    pass


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def redirect_uri() -> str:
    return f"{settings.backend_public_url.rstrip('/')}{settings.api_prefix}/fsp/callback"


def authorize_url(state: str, nonce: str, challenge: str) -> str:
    q = urlencode({
        "client_id": settings.fsp_client_id, "response_type": "code", "scope": "openid profile fsp",
        "redirect_uri": redirect_uri(), "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    return f"{settings.fsp_oidc_issuer.rstrip('/')}/protocol/openid-connect/auth?{q}"


def exchange_code(code: str, verifier: str) -> dict:
    url = f"{settings.fsp_internal}/protocol/openid-connect/token"
    try:
        r = httpx.post(url, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
            "client_id": settings.fsp_client_id, "client_secret": settings.fsp_client_secret, "code_verifier": verifier,
        }, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        raise FspError(f"ФСП ID недоступен: {exc}") from exc
    if r.status_code != 200:
        raise FspError(f"ФСП ID отклонил код авторизации ({r.status_code})")
    return r.json()


def verify_id_token(id_token: str, nonce: str) -> dict:
    jwks = jwt.PyJWKClient(f"{settings.fsp_internal}/protocol/openid-connect/certs")
    try:
        key = jwks.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=settings.fsp_client_id,
                            issuer=settings.fsp_oidc_issuer.rstrip("/"))
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise FspError(f"Некорректный id_token ФСП ID: {exc}") from exc
    if claims.get("nonce") != nonce:
        raise FspError("Несовпадение nonce в id_token")
    return claims


def fsp_id_from_claims(claims: dict) -> str:
    # В Keycloak ФСП идентификатор участника удобно отдавать атрибутом пользователя через mapper «fsp_id».
    return claims.get("fsp_id") or claims.get("preferred_username") or claims["sub"]


def fetch_participant(fsp_id: str, access_token: str | None = None) -> dict | None:
    """Профиль участника и его достижения из реестра ФСП. None — участник не найден (нет истории)."""
    headers = {"X-API-Key": settings.fsp_registry_api_key}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        r = httpx.get(f"{settings.fsp_registry_url.rstrip('/')}/participants/{fsp_id}", headers=headers, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        raise FspError(f"Реестр ФСП недоступен: {exc}") from exc
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise FspError(f"Реестр ФСП вернул {r.status_code}")
    return r.json()
