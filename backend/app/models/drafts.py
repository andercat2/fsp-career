"""Черновики заданий от LLM: пакеты генерации и сами черновики, которые проверяет эксперт.

Принятый черновик становится статичным семейством банка со статусом «пилотное» (item_stats.status = pretest):
кандидаты его видят, но на оценку оно не влияет, пока трудность не откалибрована по ответам."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class DraftBatch(Base):
    """Пакет генерации: параметры запроса администратора и прогресс фоновой задачи."""

    __tablename__ = "item_draft_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    specialization: Mapped[str] = mapped_column(String(40))
    domain: Mapped[str | None] = mapped_column(String(40))  # None — разделы по долям состава теста
    level: Mapped[int] = mapped_column(Integer)
    topic_hint: Mapped[str | None] = mapped_column(String(200))
    requested: Mapped[int] = mapped_column(Integer)
    done: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | failed
    source: Mapped[str] = mapped_column(String(20))  # llm | demo
    model: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ItemDraft(Base):
    """Черновик вопроса с выбором одного ответа. original — как предложила модель, остальные поля — текущая версия
    (после правок эксперта). checks — автоматические проверки и самопроверка модели."""

    __tablename__ = "item_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("item_draft_batches.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # llm | demo
    model: Mapped[str | None] = mapped_column(String(80))
    specialization: Mapped[str] = mapped_column(String(40))
    domain: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="single")
    topic: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text)
    code_lang: Mapped[str | None] = mapped_column(String(20))
    options: Mapped[list] = mapped_column(JSON)  # 4 варианта ответа
    correct: Mapped[int] = mapped_column(Integer)  # индекс правильного варианта
    explanation: Mapped[str] = mapped_column(Text, default="")
    original: Mapped[dict] = mapped_column(JSON)
    checks: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | accepted | rejected
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(String(200))
    family_id: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
