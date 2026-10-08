"""Админка: черновики заданий от LLM с проверкой экспертом — пополнение банка пилотными вопросами."""
from fastapi import APIRouter, HTTPException

from app.api.deps import DB, Admin
from app.models import DraftBatch
from app.schemas import DraftBatchIn, DraftEditIn, DraftRejectIn, Message
from app.services.testing import drafting

router = APIRouter(prefix="/admin/item-drafts", tags=["Администрирование: черновики заданий"])


@router.get("/options", summary="Специализации, разделы теста, уровни и режим LLM для формы генерации")
def options(_: Admin):
    return drafting.options()


@router.post("/batches", status_code=202, summary="Запустить подготовку черновиков (фоновая задача)",
             responses={409: {"model": Message}, 422: {"model": Message}})
def create_batch(data: DraftBatchIn, user: Admin, db: DB):
    """Модель пишет вопросы с выбором одного ответа; черновики появляются в очереди по мере готовности. Без LLM —
    демо-режим: черновики из заранее сгенерированного набора. Персональные данные модели не передаются."""
    b = drafting.start_batch(db, user, data.specialization, data.domain, data.level, data.count, data.topic)
    return drafting.batch_view(b)


@router.get("/batches/{bid}", summary="Прогресс пакета генерации", responses={404: {"model": Message}})
def batch(bid: int, _: Admin, db: DB):
    b = db.get(DraftBatch, bid)
    if b is None:
        raise HTTPException(404, "Пакет не найден")
    return drafting.batch_view(b)


@router.get("", summary="Черновики по статусу: pending — на проверке, accepted, rejected, all")
def list_drafts(_: Admin, db: DB, status: str = "pending"):
    if status not in ("pending", "accepted", "rejected", "all"):
        raise HTTPException(422, "Неизвестный статус")
    return drafting.list_drafts(db, status)


@router.post("/{did}/accept", summary="Принять черновик как есть или с правками эксперта",
             responses={404: {"model": Message}, 409: {"model": Message}, 422: {"model": Message}})
def accept(did: int, user: Admin, db: DB, data: DraftEditIn | None = None):
    """Без тела — как есть; с телом — версия эксперта. Вопрос становится пилотным семейством банка: кандидаты его
    видят, на оценку он не влияет, пока трудность не откалибрована по ответам."""
    d = drafting.accept(db, user, did, data.model_dump() if data else None)
    return drafting.draft_view(d)


@router.post("/{did}/reject", summary="Отклонить черновик с причиной",
             responses={404: {"model": Message}, 409: {"model": Message}})
def reject(did: int, data: DraftRejectIn, user: Admin, db: DB):
    return drafting.draft_view(drafting.reject(db, user, did, data.reason))
