from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    **({} if _is_sqlite else {"pool_size": settings.db_pool_size, "max_overflow": settings.db_max_overflow,
                              "pool_timeout": settings.db_pool_timeout}),
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def startup_lock() -> Iterator[None]:
    """Подготовка БД при старте (схема, наполнение, синхронизация) — по очереди в каждом процессе uvicorn: иначе
    несколько воркеров одновременно создавали бы схему и демо-данные. В PostgreSQL — advisory lock."""
    if _is_sqlite:
        yield
        return
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(727001)"))
        conn.commit()
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(727001)"))
            conn.commit()


def ensure_indexes() -> list[str]:
    """Индексы, объявленные в моделях после создания таблиц: create_all создаёт их только для новых таблиц."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    created = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {ix["name"] for ix in insp.get_indexes(table.name)}
        for ix in table.indexes:
            if ix.name and ix.name not in have:
                ix.create(engine, checkfirst=True)
                created.append(ix.name)
    return created


def ensure_columns() -> list[str]:
    """Лёгкая миграция для стенда: столбцы, добавленные в модели после создания БД, дописываются ALTER TABLE.
    Только добавление (без изменения и удаления) — существующие данные не затрагиваются."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    added = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl_type}'))
                added.append(f"{table.name}.{col.name}")
    return added


async def get_db() -> AsyncIterator[Session]:
    """Сессия БД на запрос. Асинхронная зависимость — намеренно: синхронные обработчики FastAPI выполняются в пуле
    потоков, и если бы закрытие сессии тоже ждало свободный поток, то при всплеске нагрузки потоки, ожидающие
    соединение из пула, заняли бы весь пул потоков, а вернуть соединение было бы некому — взаимоблокировка до
    таймаута пула (найдено нагрузочным тестом, loadtest/). Закрытие сессии — короткая операция в цикле событий."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
