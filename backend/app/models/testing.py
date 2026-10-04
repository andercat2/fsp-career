from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow


class TestSession(Base):
    __tablename__ = "test_sessions"
    __test__ = False  # не путать pytest

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    specialization: Mapped[str] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(40))
    target_grade: Mapped[str] = mapped_column(String(20))
    blueprint: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress|completed|abandoned
    theta: Mapped[float] = mapped_column(Float, default=0.0)
    se: Mapped[float] = mapped_column(Float, default=1.5)
    n_items: Mapped[int] = mapped_column(Integer, default=0)
    n_correct: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    responses = relationship("TestResponse", back_populates="session", order_by="TestResponse.seq")


class TestResponse(Base):
    __tablename__ = "test_responses"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    family_id: Mapped[str] = mapped_column(String(80), index=True)
    domain: Mapped[str] = mapped_column(String(40))
    variant_seed: Mapped[str] = mapped_column(String(32))
    scored: Mapped[bool] = mapped_column(Boolean, default=True)  # False — пилотное (pretest) задание
    payload: Mapped[dict] = mapped_column(JSON)  # что видел кандидат (без ключа)
    answer_key: Mapped[dict] = mapped_column(JSON)  # хранится только на сервере
    answer: Mapped[dict | list | str | float | None] = mapped_column(JSON)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    presented_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime)
    time_ms: Mapped[int | None] = mapped_column(Integer)
    theta_after: Mapped[float | None] = mapped_column(Float)
    se_after: Mapped[float | None] = mapped_column(Float)

    session = relationship("TestSession", back_populates="responses")


class ItemStat(Base):
    """Онлайн-статистика семейства заданий: экспозиция, наблюдаемая решаемость, дрейф (признак утечки)."""

    __tablename__ = "item_stats"

    family_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | pretest | flagged | retired
    a: Mapped[float] = mapped_column(Float)
    b: Mapped[float] = mapped_column(Float)
    c: Mapped[float] = mapped_column(Float)
    exposures: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    expected_correct: Mapped[float] = mapped_column(Float, default=0.0)  # сумма P(θ) по модели
    expected_var: Mapped[float] = mapped_column(Float, default=0.0)  # сумма P(1−P) — для z-статистики дрейфа
    drift_z: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
