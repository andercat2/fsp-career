"""Точка входа FastAPI. Документация API: /docs (Swagger UI), /redoc, спецификация: /openapi.json."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — регистрация моделей в метаданных
from app.api import auth, candidate, candidate_actions, employer, fsp, public, reference, testing
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def _warmup() -> None:
    """Обучение классификатора специализаций и загрузка NER-модели занимают несколько секунд — делаем в фоне."""
    from app.services.nlp.resume_parser import _natasha
    from app.services.nlp.vacancy_parser import _model
    from app.services.testing.integrity import build_index

    _model()
    _natasha()
    log.info("NLP-модели загружены")
    log.info("Индекс детектора «чужого варианта»: %d семейств", len(build_index()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    from app.core.db import ensure_columns

    added = ensure_columns()
    if added:
        log.info("Добавлены столбцы: %s", ", ".join(added))
    from app.services.testing.service import sync_item_stats, sync_unconfirmed

    with SessionLocal() as db:
        sync_item_stats(db)
        if settings.seed_demo:
            from app.seed.seed import seed_if_empty

            seed_if_empty(db)
        if n := sync_unconfirmed(db):
            log.info("Статус «грейд не подтверждён» восстановлен из истории тестов: %d резюме", n)
        if settings.seed_demo:
            from app.seed.seed import upgrade_demo_data

            upgrade_demo_data(db)
    threading.Thread(target=_warmup, daemon=True).start()
    yield


tags_metadata = [
    {"name": "Аутентификация", "description": "Регистрация по e-mail с подтверждением, JWT."},
    {"name": "Кандидат: профиль", "description": "Профиль, резюме (PDF с автораспознаванием), приватность, согласия."},
    {"name": "Кандидат: опрос и тестирование", "description": "Опрос, адаптивное тестирование (CAT/IRT), грейд."},
    {"name": "Кандидат: приглашения, вакансии, задания", "description": "Входящие приглашения, отклики, задания."},
    {"name": "Работодатель", "description": "Компания, потребности, подборки, банк кандидатов, приглашения."},
    {"name": "Интеграция с ФСП", "description": "Привязка ФСП ID (OIDC, совместимо с Keycloak), реестр достижений."},
    {"name": "Справочники", "description": "Специализации, грейды, навыки, отрасли."},
    {"name": "Публичное: методика и оценка", "description": "Результаты валидации и стенд оценки ранжирования."},
]

app = FastAPI(
    title="ФСП Карьера — API",
    version="1.0.0",
    description="Платформа подбора ИТ-специалистов с обратной механикой: кандидаты распределяются по категориям "
                "(специализация × грейд) по результатам адаптивного тестирования, работодатель сам находит категорию "
                "и выходит на конкретного кандидата с предложением и обязательной вилкой зарплаты.",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])

for r in (auth, reference, candidate, testing, candidate_actions, fsp, employer, public):
    app.include_router(r.router, prefix=settings.api_prefix)


@app.get("/health", tags=["Служебное"], summary="Проверка работоспособности")
def health():
    return {"status": "ok"}
