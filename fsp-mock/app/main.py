"""Mock-сервис ФСП: OIDC-провайдер «ФСП ID» и API реестра достижений участников.

Эндпоинты OIDC повторяют пути Keycloak (realm «fsp»), поэтому платформа без изменений кода подключается к
настоящему Keycloak ФСП — достаточно поменять адрес issuer и учётные данные клиента.
  GET  /realms/fsp/.well-known/openid-configuration
  GET  /realms/fsp/protocol/openid-connect/auth      — страница входа участника
  POST /realms/fsp/protocol/openid-connect/token     — обмен кода (PKCE S256 + client_secret)
  GET  /realms/fsp/protocol/openid-connect/certs     — JWKS (RS256)
  GET  /realms/fsp/protocol/openid-connect/userinfo
Реестр (схема данных — предложение команды, см. docs):
  GET  /registry/api/v1/participants/{fsp_id}         — профиль участника и достижения
  GET  /registry/api/v1/participants?q=               — поиск (для демонстрации)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
PUBLIC_ISSUER = os.getenv("PUBLIC_ISSUER", "http://localhost:8090/realms/fsp").rstrip("/")
CLIENTS = {os.getenv("CLIENT_ID", "fsp-career"): os.getenv("CLIENT_SECRET", "fsp-career-secret")}
REDIRECT_PREFIXES = [p.strip() for p in os.getenv("ALLOWED_REDIRECT_PREFIXES",
                                                  "http://localhost:8000/,http://localhost:8080/,http://127.0.0.1:8000/").split(",")]
API_KEYS = {os.getenv("REGISTRY_API_KEY", "registry-demo-key")}
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "fsp12345")
ALIASES = {"alice": "FSP-DEMO-000001", "gleb": "FSP-DEMO-000002"}

PARTICIPANTS: dict[str, dict] = {
    p["fsp_id"]: {k: v for k, v in p.items() if k != "quality"}
    for p in json.loads((BASE / "data" / "participants.json").read_text(encoding="utf-8"))
}
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = secrets.token_hex(8)
_CODES: dict[str, dict] = {}
_TOKENS: dict[str, str] = {}  # access_token -> fsp_id

app = FastAPI(title="ФСП ID (mock) и реестр достижений", version="1.0.0")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


def _sign(claims: dict) -> str:
    return jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": _KID})


@app.get("/realms/fsp/.well-known/openid-configuration")
def discovery():
    base = f"{PUBLIC_ISSUER}/protocol/openid-connect"
    return {
        "issuer": PUBLIC_ISSUER, "authorization_endpoint": f"{base}/auth", "token_endpoint": f"{base}/token",
        "userinfo_endpoint": f"{base}/userinfo", "jwks_uri": f"{base}/certs",
        "response_types_supported": ["code"], "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"], "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email", "fsp"],
        "claims_supported": ["sub", "name", "email", "fsp_id", "preferred_username"],
    }


@app.get("/realms/fsp/protocol/openid-connect/certs")
def certs():
    pub = _KEY.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": _KID, "n": _b64(pub.n), "e": _b64(pub.e)}]}


def _check_client(client_id: str, redirect_uri: str):
    if client_id not in CLIENTS:
        raise HTTPException(400, "unknown client_id")
    if not any(redirect_uri.startswith(p) for p in REDIRECT_PREFIXES):
        raise HTTPException(400, "redirect_uri is not allowed for this client")


@app.get("/realms/fsp/protocol/openid-connect/auth", response_class=HTMLResponse)
def auth_page(request: Request, client_id: str, redirect_uri: str, state: str, nonce: str = "",
              code_challenge: str = "", code_challenge_method: str = "S256", response_type: str = "code",
              scope: str = "openid", error: str | None = None):
    _check_client(client_id, redirect_uri)
    demo = [PARTICIPANTS[ALIASES["alice"]], PARTICIPANTS[ALIASES["gleb"]]]
    others = [p for p in PARTICIPANTS.values() if not p["fsp_id"].startswith("FSP-DEMO")][:6]
    return templates.TemplateResponse(request, "login.html", {
        "q": {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce,
              "code_challenge": code_challenge, "code_challenge_method": code_challenge_method},
        "demo": demo, "others": others, "error": error, "password": DEMO_PASSWORD,
    })


@app.post("/realms/fsp/protocol/openid-connect/auth")
def auth_submit(client_id: str = Form(...), redirect_uri: str = Form(...), state: str = Form(...),
                nonce: str = Form(""), code_challenge: str = Form(""), code_challenge_method: str = Form("S256"),
                username: str = Form(...), password: str = Form(...), action: str = Form("login")):
    _check_client(client_id, redirect_uri)
    if action == "cancel":
        return RedirectResponse(f"{redirect_uri}?{urlencode({'error': 'access_denied', 'state': state})}", 302)
    fsp_id = ALIASES.get(username.strip().lower(), username.strip())
    if fsp_id not in PARTICIPANTS or password != DEMO_PASSWORD:
        q = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce,
                       "code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
                       "error": "Неверный логин или пароль"})
        return RedirectResponse(f"{PUBLIC_ISSUER}/protocol/openid-connect/auth?{q}", 303)
    code = secrets.token_urlsafe(24)
    _CODES[code] = {"fsp_id": fsp_id, "client_id": client_id, "redirect_uri": redirect_uri, "nonce": nonce,
                    "challenge": code_challenge, "exp": time.time() + 120}
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", 302)


@app.post("/realms/fsp/protocol/openid-connect/token")
def token(grant_type: str = Form(...), code: str = Form(...), redirect_uri: str = Form(...),
          client_id: str = Form(...), client_secret: str = Form(""), code_verifier: str = Form("")):
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, 400)
    if CLIENTS.get(client_id) != client_secret:
        return JSONResponse({"error": "invalid_client"}, 401)
    data = _CODES.pop(code, None)
    if not data or data["exp"] < time.time() or data["redirect_uri"] != redirect_uri or data["client_id"] != client_id:
        return JSONResponse({"error": "invalid_grant"}, 400)
    if data["challenge"]:
        calc = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        if calc != data["challenge"]:
            return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, 400)
    p = PARTICIPANTS[data["fsp_id"]]
    now = int(time.time())
    base = {"iss": PUBLIC_ISSUER, "sub": p["fsp_id"], "iat": now, "exp": now + 300, "fsp_id": p["fsp_id"],
            "preferred_username": p["fsp_id"], "name": p["full_name"], "email": p["email"], "email_verified": True}
    access = _sign(base | {"aud": "fsp-registry", "typ": "Bearer", "scope": "openid profile fsp"})
    _TOKENS[access] = p["fsp_id"]
    id_token = _sign(base | {"aud": client_id, "typ": "ID", "nonce": data["nonce"]})
    return {"access_token": access, "id_token": id_token, "token_type": "Bearer", "expires_in": 300,
            "scope": "openid profile fsp"}


@app.get("/realms/fsp/protocol/openid-connect/userinfo")
def userinfo(authorization: str = Header("")):
    fsp_id = _TOKENS.get(authorization.removeprefix("Bearer ").strip())
    if not fsp_id:
        raise HTTPException(401, "invalid token")
    p = PARTICIPANTS[fsp_id]
    return {"sub": fsp_id, "fsp_id": fsp_id, "name": p["full_name"], "email": p["email"]}


def _authorized(fsp_id: str, api_key: str | None, authorization: str | None) -> bool:
    if api_key in API_KEYS:
        return True
    tok = (authorization or "").removeprefix("Bearer ").strip()
    return _TOKENS.get(tok) == fsp_id


@app.get("/registry/api/v1/participants/{fsp_id}")
def participant(fsp_id: str, x_api_key: str | None = Header(None), authorization: str | None = Header(None)):
    if not _authorized(fsp_id, x_api_key, authorization):
        raise HTTPException(401, "API key or participant token required")
    p = PARTICIPANTS.get(fsp_id)
    if not p:
        raise HTTPException(404, "participant not found")
    return p


@app.get("/registry/api/v1/participants")
def search(q: str = "", x_api_key: str | None = Header(None), limit: int = 20):
    if x_api_key not in API_KEYS:
        raise HTTPException(401, "API key required")
    ql = q.lower()
    res = [p for p in PARTICIPANTS.values() if ql in p["full_name"].lower() or ql in p["fsp_id"].lower()]
    return {"total": len(res), "items": res[:limit]}


@app.get("/", response_class=HTMLResponse)
def index():
    return f"""<html><head><meta charset="utf-8"><title>ФСП ID (mock)</title></head>
<body style="font-family:Montserrat,Arial,sans-serif;max-width:720px;margin:40px auto;color:#1C1D22">
<h1 style="color:#310F53">ФСП ID — демонстрационный стенд</h1>
<p>OIDC-провайдер, совместимый по путям с Keycloak (realm <b>fsp</b>), и API реестра достижений.</p>
<ul><li><a href="/realms/fsp/.well-known/openid-configuration">openid-configuration</a></li>
<li><a href="/docs">OpenAPI</a></li></ul><p>Участников в реестре: {len(PARTICIPANTS)}.</p></body></html>"""


@app.get("/health")
def health():
    return {"status": "ok", "participants": len(PARTICIPANTS)}
