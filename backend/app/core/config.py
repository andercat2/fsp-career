"""Конфигурация приложения. Все параметры переопределяются переменными окружения (см. .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ФСП Карьера"
    api_prefix: str = "/api/v1"
    environment: str = "dev"

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"

    secret_key: str = "dev-secret-change-me-please-0123456789abcdef"
    access_token_expire_minutes: int = 60 * 12
    jwt_algorithm: str = "HS256"

    # Почта: в dev-режиме код подтверждения дублируется в лог и в ответ API,
    # в docker-compose письма уходят в Mailpit (http://localhost:8025).
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_from: str = "noreply@fsp-career.local"
    smtp_user: str | None = None  # внешний почтовый сервер: логин, пароль и STARTTLS (порт 587)
    smtp_password: str | None = None
    smtp_starttls: bool = False
    email_dev_mode: bool = True
    # «Попробовать как кандидат»: одноразовый аккаунт кандидата без регистрации (демо и жюри); в продуктиве — false
    guest_mode: bool = True

    frontend_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:8080,http://127.0.0.1:5173"

    # ФСП ID (OIDC, совместимо с Keycloak). issuer — адрес для браузера,
    # internal — адрес для межсервисных вызовов (в docker-сети отличается).
    fsp_oidc_issuer: str = "http://localhost:8090/realms/fsp"
    fsp_oidc_internal_url: str | None = "http://127.0.0.1:8090/realms/fsp"
    fsp_client_id: str = "fsp-career"
    fsp_client_secret: str = "fsp-career-secret"
    fsp_registry_url: str = "http://127.0.0.1:8090/registry/api/v1"
    fsp_registry_api_key: str = "registry-demo-key"
    fsp_enabled: bool = True

    # Бизнес-правила
    grade_change_cooldown_days: int = 30  # смена грейда — не чаще раза в месяц
    same_level_retake_days: int = 30  # повторная попытка теста того же уровня
    invitation_ttl_days: int = 14
    invitations_per_day_limit: int = 60
    task_offer_interval_days: int = 7  # регулярные задания — раз в неделю

    # Производительность. Пул соединений с БД — по числу потоков обработчиков в процессе (AnyIO: 40), иначе под
    # нагрузкой запросы ждут соединение (validation: loadtest/). Процессов uvicorn — WEB_CONCURRENCY в docker-compose
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout: int = 15

    seed_demo: bool = True
    seed_candidates: int = 700

    # Песочница для задач с кодом: в Docker — отдельный контейнер без сети, адрес unix:///путь/к/сокету (или
    # http://хост:порт); без него код исполняется локальным подпроцессом с таймаутом — только для разработки и
    # автотестов (sandbox_local)
    sandbox_url: str | None = None
    sandbox_token: str = "sandbox-demo-token"
    sandbox_local: bool = True

    # Черновики заданий от LLM (админка): любой OpenAI-совместимый API — Ollama, vLLM, облачные модели. Пусто или
    # сервис недоступен — демо-режим с заранее сгенерированными черновиками. Модель получает только раздел, уровень
    # и тему — без персональных данных. reasoning_effort "none" отключает «рассуждения» (быстрее, но хуже качество)
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "qwen3:14b"
    llm_reasoning_effort: str | None = None
    llm_timeout: int = 300
    llm_self_check: bool = True

    @property
    def fsp_internal(self) -> str:
        return (self.fsp_oidc_internal_url or self.fsp_oidc_issuer).rstrip("/")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
