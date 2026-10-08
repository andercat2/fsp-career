"""Клиент LLM для подготовки банка заданий: любой OpenAI-совместимый API (Ollama, vLLM, облачные модели).

Используется только в админке — для черновиков новых вопросов, которые затем проверяет эксперт. В тестировании
кандидатов и подборе модель не участвует, персональные данные ей не передаются: в запросе только раздел теста,
уровень сложности и тема."""
from __future__ import annotations

import json
import re
import time

import httpx

from app.core.config import settings

STATUS_TTL_SEC = 30
_status_cache: dict = {"at": 0.0, "value": None}


class LLMError(RuntimeError):
    pass


def _base() -> str:
    return (settings.llm_base_url or "").rstrip("/")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}


def status(force: bool = False) -> dict:
    """Доступна ли модель: список моделей сервиса (GET /models), результат кэшируется на 30 секунд."""
    if not settings.llm_base_url:
        return {"available": False, "model": settings.llm_model, "reason": "LLM не настроена (LLM_BASE_URL пуст)"}
    now = time.time()
    if not force and _status_cache["value"] is not None and now - _status_cache["at"] < STATUS_TTL_SEC:
        return _status_cache["value"]
    try:
        r = httpx.get(f"{_base()}/models", headers=_headers(), timeout=5)
        r.raise_for_status()
        ids = {m.get("id") for m in r.json().get("data", [])}
        ok = settings.llm_model in ids
        value = {"available": ok, "model": settings.llm_model,
                 "reason": None if ok else f"модель {settings.llm_model} не найдена в сервисе"}
    except (httpx.HTTPError, ValueError) as exc:
        value = {"available": False, "model": settings.llm_model, "reason": f"сервис недоступен ({exc.__class__.__name__})"}
    _status_cache.update(at=now, value=value)
    return value


def chat_json(messages: list[dict], schema: dict, *, temperature: float = 0.7) -> dict:
    """Запрос к модели с ответом строго по JSON-схеме (structured outputs)."""
    body: dict = {"model": settings.llm_model, "messages": messages, "temperature": temperature,
                  "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": schema}}}
    if settings.llm_reasoning_effort:
        body["reasoning_effort"] = settings.llm_reasoning_effort
    try:
        r = httpx.post(f"{_base()}/chat/completions", json=body, headers=_headers(), timeout=settings.llm_timeout)
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM недоступна ({exc.__class__.__name__})") from exc
    if r.status_code >= 400:
        raise LLMError(f"LLM вернула ошибку {r.status_code}: {r.text[:200]}")
    try:
        content = r.json()["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError("неожиданный формат ответа LLM") from exc
    return parse_json(content)


def parse_json(text: str) -> dict:
    """JSON из ответа модели: без блока «рассуждений» и обрамления ```json."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise LLMError("в ответе модели нет JSON")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"некорректный JSON в ответе модели: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LLMError("ответ модели — не JSON-объект")
    return data
