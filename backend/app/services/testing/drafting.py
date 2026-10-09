"""Черновики заданий от LLM с проверкой экспертом — пополнение банка без потери сопоставимости.

Конвейер: администратор выбирает специализацию, раздел теста, уровень и число вопросов → модель пишет черновики
вопросов с выбором одного ответа (фоновая задача, черновики появляются по мере готовности) → автоматические проверки
(формат, повтор правильного ответа в условии, «самый длинный вариант — верный», похожие задания в банке) и
самопроверка модели (нет ли второго верного варианта) → эксперт принимает как есть, правит вопрос и ответы или
отклоняет → принятый вопрос становится статичным семейством банка со статусом «пилотное»: кандидаты его видят, на
оценку он не влияет, пока трудность не откалибрована по ответам (calibrate_pretest, от 40 ответов).

Модель получает только раздел, уровень, тему и примеры из банка — персональных данных в запросах нет. Без LLM
(LLM_BASE_URL пуст или сервис недоступен) работает демо-режим: черновики из заранее сгенерированного набора
(app/seed/llm_demo_drafts.json, собран этим же конвейером: python -m app.services.testing.drafting build-demo).
"""
from __future__ import annotations

import json
import logging
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal, utcnow
from app.models import DraftBatch, ItemDraft, ItemStat, TestResponse, User
from app.services import llm
from app.services.notify import audit
from app.services.reference.taxonomy import DOMAINS, SPEC_BY_CODE, SPEC_NAMES, SPECIALIZATIONS
from app.services.testing.bank import BY_DOMAIN, REGISTRY, add_drafted_family

log = logging.getLogger("app.drafting")

PROMPT_VERSION = "v1"
MAX_BATCH = 10
STALE_BATCH = timedelta(hours=1)
SIMILAR = 0.6  # косинусная близость текста вопроса к заданию банка или другому черновику — предупреждение
LEVELS = {
    1: ("Стажёр", "базовые понятия и определения — то, что знает стажёр после курса"),
    2: ("Junior", "типовые конструкции и чтение простого кода; ответ виден без хитростей"),
    3: ("Junior/Middle", "поведение в типичных, но не очевидных случаях; распространённые ошибки"),
    4: ("Middle", "нетривиальные случаи, выбор подходящего решения, отладка по симптомам"),
    5: ("Senior", "тонкие эффекты, компромиссы архитектуры и производительности, редкие сбои"),
}
REJECT_REASONS = ["Неверный правильный ответ", "Есть второй верный вариант", "Двусмысленная формулировка",
                  "Не тот уровень сложности", "Дубль существующего задания", "Не по теме раздела", "Другое"]
CODE_LANGS = ["python", "javascript", "typescript", "java", "go", "sql", "bash", "yaml", "dockerfile", "json", "html",
              "css"]
DEMO_FILE = Path(__file__).resolve().parents[2] / "seed" / "llm_demo_drafts.json"

SYSTEM = ("Ты — методист, который составляет вопросы для адаптивного теста ИТ-специалистов. Пиши по-русски, "
          "грамотно и кратко; термины, код и названия технологий — как принято в индустрии. Вопрос должен "
          "однозначно проверять знание, а не внимательность к формулировке. Ответ — строго JSON по схеме.")
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"}, "prompt": {"type": "string"},
        "code": {"type": ["string", "null"]}, "code_lang": {"type": ["string", "null"]},
        "correct": {"type": "string"},
        "distractors": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "explanation": {"type": "string"},
    },
    "required": ["topic", "prompt", "code", "code_lang", "correct", "distractors", "explanation"],
}
LETTERS = "ABCD"  # варианты ответа в интерфейсе и в запросе рецензенту
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["ok", "problem"]},
                   "also_correct": {"type": "array", "items": {"type": "string", "enum": list(LETTERS)}},
                   "issues": {"type": "array", "items": {"type": "string"}}},
    "required": ["verdict", "also_correct", "issues"],
}

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-drafts")  # одна модель — один запрос за раз


def _submit(fn, *args) -> None:
    _EXECUTOR.submit(fn, *args)


# ---------------------------------------------------------------- справочник для формы и режим работы

def spec_domains(spec: str) -> dict[str, float]:
    """Разделы теста специализации с долями; «основной язык» делится поровну между языками специализации."""
    sp = SPEC_BY_CODE[spec]
    out: dict[str, float] = {}
    for dom, w in sp["blueprint"].items():
        keys = sp["languages"] if dom == "$lang" else [dom]
        for k in keys:
            out[k] = out.get(k, 0.0) + w / len(keys)
    total = sum(out.values())
    return {k: round(v / total, 4) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def _demo_set() -> dict:
    try:
        return json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"model": None, "items": []}


def mode() -> dict:
    """llm — модель доступна; demo — черновики из заранее сгенерированного набора."""
    st = llm.status()
    if st["available"]:
        return {"mode": "llm", "model": st["model"], "reason": None}
    demo = _demo_set()
    return {"mode": "demo", "model": demo.get("model"), "reason": st["reason"], "demo_items": len(demo["items"])}


def options() -> dict:
    return {
        "specializations": [{"code": sp["code"], "name": sp["name"], "direction": sp["direction"], "domains": [
            {"code": d, "name": DOMAINS[d], "weight": w, "families": len(BY_DOMAIN.get(d, []))}
            for d, w in spec_domains(sp["code"]).items()]} for sp in SPECIALIZATIONS],
        "levels": [{"level": k, "grade": g, "description": d} for k, (g, d) in LEVELS.items()],
        "max_batch": MAX_BATCH, "reject_reasons": REJECT_REASONS, "code_langs": CODE_LANGS, "llm": mode(),
    }


# ---------------------------------------------------------------- генерация

def _example(dom: str) -> str:
    """Один статичный вопрос раздела из банка — образец стиля для модели."""
    fam = next((f for f in BY_DOMAIN.get(dom, []) if not f.parametric and f.kind == "single"), None)
    if fam is None:
        return ""
    r = fam.render(7)
    right = next(o["text"] for o in r.options if o["id"] == r.key)
    wrong = [o["text"] for o in r.options if o["id"] != r.key]
    return f"Пример стиля из банка: вопрос «{r.prompt}»; верный ответ «{right}»; неверные: «{'», «'.join(wrong)}»."


def _question_messages(spec: str, dom: str, level: int, topic: str | None, avoid: list[str]) -> list[dict]:
    grade, desc = LEVELS[level]
    taken = sorted({f.topic for f in BY_DOMAIN.get(dom, [])})[:30] + avoid
    user = "\n".join(filter(None, [
        "Составь один вопрос с выбором одного ответа для теста ИТ-специалистов.",
        f"Специализация: {SPEC_NAMES[spec]}. Раздел теста: {DOMAINS[dom]}.",
        f"Уровень сложности: {level} из 5 — {grade}: {desc}.",
        f"Тема: {topic}." if topic else "Тему выбери сам.",
        f"Темы, которые уже есть (не повторяй): {'; '.join(taken)}." if taken else "",
        "Требования:",
        "- ровно один правильный ответ и три неверных: правдоподобных, но однозначно неверных;",
        "- проверяй понимание, а не память на формулировки; без вариантов «все ответы верны» и «ни один»;",
        "- правильный ответ не повторяет дословно текст или код условия и не выделяется длиной;",
        "- нужен код — короткий фрагмент (до 15 строк) в поле code и язык в code_lang, иначе code и code_lang = null;",
        "- explanation — одно-два предложения: почему верный ответ верен.",
        _example(dom),
    ]))
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _clean(s) -> str:
    return re.sub(r"\s+\n", "\n", str(s or "")).strip()


def normalize(data: dict) -> dict:
    """Ответ модели → поля черновика; ValueError, если вопрос непригоден даже как черновик."""
    q = {k: _clean(data.get(k)) for k in ("topic", "prompt", "correct", "explanation")}
    q["code"] = None if _clean(data.get("code")).lower() in ("", "null", "none") else _clean(data.get("code"))
    lang = None if _clean(data.get("code_lang")).lower() in ("", "null", "none") else _clean(data.get("code_lang")).lower()
    q["code_lang"] = lang if q["code"] else None
    seen = {q["correct"].lower()}
    wrong = []
    for d in data.get("distractors") or []:
        t = _clean(d)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            wrong.append(t)
    q["distractors"] = wrong[:3]
    if len(q["prompt"]) < 10 or not q["correct"] or len(q["distractors"]) < 3:
        raise ValueError("модель вернула неполный вопрос")
    q["topic"] = q["topic"][:200] or q["prompt"][:60]
    return q


def generate_question(spec: str, dom: str, level: int, topic: str | None = None, avoid: list[str] | None = None) -> dict:
    data = llm.chat_json(_question_messages(spec, dom, level, topic, avoid or []), QUESTION_SCHEMA)
    return normalize(data)


def self_check(prompt: str, code: str | None, opts: list[str], correct: int) -> dict:
    """Модель-рецензент: однозначен ли вопрос и верен ли ключ. Это подсказка эксперту, решение принимает человек.
    Варианты подписаны буквами, как в интерфейсе, чтобы замечания рецензента ссылались на те же буквы."""
    listing = "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(opts))
    user = (f"Проверь тестовый вопрос как строгий эксперт.\nВопрос: {prompt}\n"
            + (f"Код:\n{code}\n" if code else "")
            + f"Варианты:\n{listing}\nАвтор считает верным вариант {LETTERS[correct]}.\n"
            "Ответь JSON: verdict — ok, если ровно один вариант верен и это вариант автора, иначе problem; "
            "also_correct — буквы других вариантов, которые тоже верны или верны вместо авторского; issues — кратко "
            "по-русски, что не так (неверный ключ, второй верный вариант, двусмысленность, ошибка в коде); "
            "на варианты ссылайся буквами.")
    data = llm.chat_json([{"role": "user", "content": user}], REVIEW_SCHEMA, temperature=0.1)
    also = sorted({i for i in (_option_index(x) for x in data.get("also_correct") or [])
                   if i is not None and i < len(opts) and i != correct})
    issues = [_clean(x) for x in data.get("issues") or [] if _clean(x)][:5]
    verdict = "problem" if data.get("verdict") == "problem" or also else "ok"
    return {"verdict": verdict, "also_correct": also, "issues": issues if verdict == "problem" else []}


def _option_index(x) -> int | None:
    """Ссылка на вариант ответа — буква A–D или номер с нуля (так рецензент отвечал до перехода на буквы)."""
    t = str(x).strip().upper()
    if len(t) == 1 and t in LETTERS:
        return LETTERS.index(t)
    return int(t) if t.isdigit() else None


def as_letters(text: str) -> str:
    """«Вариант 0 и 2» → «Вариант A и C»: в замечаниях демо-набора рецензент нумеровал варианты с нуля."""
    def repl(m: re.Match) -> str:
        return m.group(1) + re.sub(r"\d", lambda d: LETTERS[int(d.group())] if int(d.group()) < len(LETTERS) else d.group(),
                                   m.group(2))
    return re.sub(r"((?:[Вв]ариант\w*|[Оо]тв[её]т\w*)\s+)(\d(?:\s*(?:,|и|или)\s*\d)*)\b", repl, text)


# ---------------------------------------------------------------- автоматические проверки

def _norm(s: str) -> str:
    return " ".join(re.findall(r"\w+", (s or "").lower().replace("ё", "е")))


def _similar(text: str, others: list[tuple[str, str]]) -> tuple[float, str] | None:
    """Самый похожий текст из others [(метка, текст)] по TF-IDF символьных n-грамм."""
    if not others:
        return None
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit([text] + [t for _, t in others])
    sims = cosine_similarity(vec.transform([text]), vec.transform([t for _, t in others]))[0]
    i = int(sims.argmax())
    return float(sims[i]), others[i][0]


def auto_checks(db: Session, dom: str, prompt: str, code: str | None, opts: list[str], correct: int,
                exclude_id: int | None = None) -> list[dict]:
    """Проверки без модели: error — принять нельзя, warn — обратить внимание эксперта."""
    out = []
    if len(opts) != 4 or any(not o.strip() for o in opts):
        out.append({"level": "error", "code": "options", "text": "Нужно ровно четыре непустых варианта ответа"})
    if len({_norm(o) for o in opts}) != len(opts):
        out.append({"level": "error", "code": "duplicates", "text": "Есть одинаковые варианты ответа"})
    if not 0 <= correct < len(opts):
        out.append({"level": "error", "code": "key", "text": "Не отмечен правильный вариант"})
    if len(prompt.strip()) < 10:
        out.append({"level": "error", "code": "prompt", "text": "Слишком короткий вопрос"})
    if out:
        return out
    right = _norm(opts[correct])
    if len(right) >= 8 and right in _norm(prompt + " " + (code or "")):
        out.append({"level": "warn", "code": "leak", "text": "Правильный ответ дословно встречается в условии"})
    if any(re.search(r"\b(все|ни один)\b.*\b(вариант|ответ|перечисленн)", o.lower()) for o in opts):
        out.append({"level": "warn", "code": "all_none", "text": "Вариант вида «все ответы верны» / «ни один»"})
    others = [len(o) for i, o in enumerate(opts) if i != correct]
    if len(opts[correct]) > 1.8 * (sum(others) / len(others)) and len(opts[correct]) > 40:
        out.append({"level": "warn", "code": "longest", "text": "Правильный вариант заметно длиннее остальных — "
                                                                  "его можно угадать по длине"})
    if len(prompt) > 1500 or any(len(o) > 300 for o in opts):
        out.append({"level": "warn", "code": "length", "text": "Очень длинный вопрос или вариант ответа"})
    pool = [(f"задание банка {f.id} «{f.topic}»", f.render(1).prompt) for f in list(BY_DOMAIN.get(dom, []))
            if not f.parametric]
    pool += [(f"черновик №{d.id} «{d.topic}»", d.prompt) for d in db.scalars(
        select(ItemDraft).where(ItemDraft.domain == dom, ItemDraft.status != "rejected",
                                ItemDraft.id != (exclude_id or 0)))]
    hit = _similar(prompt, pool)
    if hit and hit[0] >= SIMILAR:
        out.append({"level": "warn", "code": "similar", "text": f"Похоже на {hit[1]} (сходство {hit[0]:.2f})"})
    return out


# ---------------------------------------------------------------- пакет генерации (фоновая задача)

def recover_batches(db: Session) -> None:
    """Пакеты, прерванные перезапуском приложения, помечаются завершёнными с ошибкой."""
    for b in db.scalars(select(DraftBatch).where(DraftBatch.status == "running")):
        b.status, b.error, b.finished_at = ("done" if b.done else "failed"), "Прервано перезапуском сервера", utcnow()
    db.commit()


def start_batch(db: Session, user: User, specialization: str, domain: str | None, level: int, count: int,
                topic: str | None) -> DraftBatch:
    if specialization not in SPEC_BY_CODE:
        raise HTTPException(422, "Неизвестная специализация")
    if domain and domain not in spec_domains(specialization):
        raise HTTPException(422, "Этот раздел не входит в состав теста специализации")
    if level not in LEVELS or not 1 <= count <= MAX_BATCH:
        raise HTTPException(422, f"Уровень — от 1 до 5, вопросов в пакете — от 1 до {MAX_BATCH}")
    running = db.scalar(select(DraftBatch).where(DraftBatch.status == "running"))
    if running and running.created_at > utcnow() - STALE_BATCH:
        raise HTTPException(409, "Модель ещё готовит предыдущий пакет — дождитесь его окончания")
    m = mode()
    batch = DraftBatch(created_by=user.id, specialization=specialization, domain=domain or None, level=level,
                       topic_hint=(topic or "").strip()[:200] or None, requested=count, source=m["mode"],
                       model=m["model"])
    db.add(batch)
    audit(db, user.id, "item_drafts_generate", "item_draft_batch", None, specialization=specialization,
          domain=domain, level=level, count=count, source=m["mode"])
    db.commit()
    _submit(run_batch, batch.id)
    return batch


def _demo_question(dom: str, level: int, used: set[str]) -> tuple[dict, dict | None, str | None]:
    items = [x for x in _demo_set()["items"] if x["domain"] == dom]
    if not items:
        raise ValueError(f"В демо-наборе нет черновиков для раздела «{DOMAINS.get(dom, dom)}»")
    items.sort(key=lambda x: (x["prompt"] in used, abs(x["level"] - level)))
    x = items[0]
    q = {k: x[k] for k in ("topic", "prompt", "code", "code_lang", "correct", "distractors", "explanation")}
    return q, x.get("review"), x.get("model")


def _save_draft(db: Session, batch: DraftBatch, dom: str, q: dict, review: dict | None, rng: random.Random,
                model: str | None) -> ItemDraft:
    opts = [q["correct"], *q["distractors"]]
    stored = (review or {}).get("options")
    if stored and sorted(stored) == sorted(opts):  # демо-набор: порядок вариантов тот, что видел рецензент
        opts = list(stored)
    else:
        rng.shuffle(opts)
    correct = opts.index(q["correct"])
    if review is None and batch.source == "llm" and settings.llm_self_check:
        try:
            review = self_check(q["prompt"], q["code"], opts, correct)
        except llm.LLMError as exc:
            review = {"verdict": "unknown", "also_correct": [], "issues": [f"Самопроверка не выполнена: {exc}"]}
    elif review is not None:  # демо-набор: самопроверка сохранена вместе с черновиком
        also = [i for i in (_option_index(x) for x in review.get("also_correct", [])) if i is not None and i != correct]
        review = {"verdict": review["verdict"], "also_correct": also, "issues": review.get("issues", [])}
    d = ItemDraft(batch_id=batch.id, source=batch.source, model=model or batch.model, specialization=batch.specialization,
                  domain=dom, level=batch.level, topic=q["topic"], prompt=q["prompt"], code=q["code"],
                  code_lang=q["code_lang"], options=opts, correct=correct, explanation=q["explanation"],
                  original={**q, "options": opts, "correct_index": correct, "prompt_version": PROMPT_VERSION},
                  checks={"auto": [], "review": review}, status="pending")
    db.add(d)
    db.flush()
    d.checks = {"auto": auto_checks(db, dom, d.prompt, d.code, opts, correct, exclude_id=d.id), "review": review}
    return d


def run_batch(batch_id: int) -> None:
    with SessionLocal() as db:
        b = db.get(DraftBatch, batch_id)
        if b is None:
            return
        try:
            rng = random.Random(batch_id * 7919)
            doms = spec_domains(b.specialization)
            plan = [b.domain] * b.requested if b.domain else rng.choices(list(doms), weights=list(doms.values()),
                                                                          k=b.requested)
            used = set(db.scalars(select(ItemDraft.prompt).where(ItemDraft.source == "demo")))
            topics: list[str] = []
            for dom in plan:
                try:
                    if b.source == "llm":
                        q, review, model = generate_question(b.specialization, dom, b.level, b.topic_hint, topics), None, None
                    else:
                        q, review, model = _demo_question(dom, b.level, used)
                    d = _save_draft(db, b, dom, q, review, rng, model)
                    topics.append(d.topic)
                    used.add(d.prompt)
                    b.done += 1
                except (llm.LLMError, ValueError) as exc:
                    log.warning("Черновик не получен (пакет %s): %s", batch_id, exc)
                    b.failed += 1
                    b.error = str(exc)[:500]
                db.commit()
            b.status = "done" if b.done else "failed"
        except Exception as exc:  # noqa: BLE001 — фоновая задача не должна оставлять пакет «в работе»
            log.exception("Пакет черновиков %s прерван", batch_id)
            db.rollback()
            b = db.get(DraftBatch, batch_id)
            b.status, b.error = ("done" if b.done else "failed"), f"Внутренняя ошибка: {exc.__class__.__name__}"
        b.finished_at = utcnow()
        db.commit()


# ---------------------------------------------------------------- решения эксперта

def _family_args(d: ItemDraft) -> dict:
    return {"fid": d.family_id, "domain": d.domain, "level": d.level, "prompt": d.prompt,
            "correct": d.options[d.correct], "wrong": [o for i, o in enumerate(d.options) if i != d.correct],
            "topic": d.topic, "code": d.code, "code_lang": d.code_lang, "explain": d.explanation}


def load_drafted_families(db: Session) -> int:
    """При старте: принятые черновики снова регистрируются в банке (банк из кода + банк из БД)."""
    n = 0
    for d in db.scalars(select(ItemDraft).where(ItemDraft.status == "accepted", ItemDraft.family_id.is_not(None))):
        add_drafted_family(**_family_args(d))
        n += 1
    return n


def _pending(db: Session, did: int) -> ItemDraft:
    d = db.get(ItemDraft, did)
    if d is None:
        raise HTTPException(404, "Черновик не найден")
    if d.status != "pending":
        raise HTTPException(409, "По этому черновику решение уже принято")
    return d


def accept(db: Session, user: User, did: int, edits: dict | None = None) -> ItemDraft:
    """Принять как есть или с правками эксперта. Вопрос становится пилотным семейством банка."""
    d = _pending(db, did)
    if edits:
        changed = any(getattr(d, k) != v for k, v in edits.items())
        for k, v in edits.items():
            setattr(d, k, v)
        d.code = (d.code or "").strip() or None
        d.code_lang = d.code_lang if d.code else None
        d.edited = d.edited or changed
    checks = auto_checks(db, d.domain, d.prompt, d.code, list(d.options), d.correct, exclude_id=d.id)
    errors = [c["text"] for c in checks if c["level"] == "error"]
    if errors:
        raise HTTPException(422, "; ".join(errors))
    d.checks = {**(d.checks or {}), "auto": checks}
    d.family_id = f"llm.{d.domain}.{d.id}"
    fam = add_drafted_family(**_family_args(d))
    if db.get(ItemStat, fam.id) is None:
        db.add(ItemStat(family_id=fam.id, status="pretest", a=fam.a, b=fam.b, c=fam.c))
    d.status, d.reviewed_by, d.reviewed_at = "accepted", user.id, utcnow()
    audit(db, user.id, "item_draft_accept", "item_draft", d.id, family_id=fam.id, edited=d.edited)
    db.commit()
    from app.services.testing.service import invalidate_params

    invalidate_params()
    return d


def reject(db: Session, user: User, did: int, reason: str) -> ItemDraft:
    d = _pending(db, did)
    d.status, d.reject_reason, d.reviewed_by, d.reviewed_at = "rejected", reason.strip()[:200] or "Другое", user.id, utcnow()
    audit(db, user.id, "item_draft_reject", "item_draft", d.id, reason=d.reject_reason)
    db.commit()
    return d


# ---------------------------------------------------------------- представления

def batch_view(b: DraftBatch) -> dict:
    return {"id": b.id, "status": b.status, "source": b.source, "model": b.model, "specialization": b.specialization,
            "domain": b.domain, "level": b.level, "requested": b.requested, "done": b.done, "failed": b.failed,
            "error": b.error, "created_at": b.created_at, "finished_at": b.finished_at}


def _checks_view(checks: dict | None) -> dict:
    checks = dict(checks or {})
    if checks.get("review"):
        checks["review"] = {**checks["review"], "issues": [as_letters(t) for t in checks["review"].get("issues", [])]}
    return checks


def draft_view(d: ItemDraft, pilot: dict | None = None) -> dict:
    grade = LEVELS.get(d.level, ("", ""))[0]
    return {"id": d.id, "batch_id": d.batch_id, "source": d.source, "model": d.model,
            "specialization": d.specialization, "specialization_name": SPEC_NAMES.get(d.specialization),
            "domain": d.domain, "domain_name": DOMAINS.get(d.domain, d.domain), "level": d.level, "level_grade": grade,
            "topic": d.topic, "prompt": d.prompt, "code": d.code, "code_lang": d.code_lang, "options": d.options,
            "correct": d.correct, "explanation": d.explanation, "checks": _checks_view(d.checks), "status": d.status,
            "edited": d.edited, "original": d.original if d.edited else None, "reject_reason": d.reject_reason,
            "family_id": d.family_id, "created_at": d.created_at, "reviewed_at": d.reviewed_at, "pilot": pilot}


def list_drafts(db: Session, status: str = "pending") -> dict:
    counts = dict(db.execute(select(ItemDraft.status, func.count()).group_by(ItemDraft.status)).all())
    q = select(ItemDraft).order_by(ItemDraft.id.desc() if status != "pending" else ItemDraft.id)
    if status != "all":
        q = q.where(ItemDraft.status == status)
    drafts = list(db.scalars(q.limit(200)))
    fids = [d.family_id for d in drafts if d.family_id]
    pilot = {}
    if fids:
        answers = dict(db.execute(select(TestResponse.family_id, func.count()).where(
            TestResponse.family_id.in_(fids), TestResponse.answered_at.is_not(None)).group_by(TestResponse.family_id)).all())
        stats = {s.family_id: s.status for s in db.scalars(select(ItemStat).where(ItemStat.family_id.in_(fids)))}
        pilot = {f: {"answers": answers.get(f, 0), "status": stats.get(f), "needed": 40} for f in fids}
    running = db.scalar(select(DraftBatch).order_by(DraftBatch.id.desc()).limit(1))
    return {"items": [draft_view(d, pilot.get(d.family_id)) for d in drafts],
            "counts": {k: counts.get(k, 0) for k in ("pending", "accepted", "rejected")},
            "batch": batch_view(running) if running else None}


# ---------------------------------------------------------------- сборка демо-набора

def build_demo(levels: tuple[int, ...] = (2, 3, 4), out: Path = DEMO_FILE) -> None:
    """Демо-набор для стендов без LLM: по одному черновику на каждый раздел и уровень, тем же конвейером
    (генерация + самопроверка). Сохраняется по мере готовности — прерванную сборку можно продолжить."""
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"items": []}
    data.update(model=settings.llm_model, prompt_version=PROMPT_VERSION)
    have = {(x["domain"], x["level"]) for x in data["items"]}
    for dom in DOMAINS:
        spec = next((sp["code"] for sp in SPECIALIZATIONS if dom in spec_domains(sp["code"])), None)
        for level in levels:
            if spec is None or (dom, level) in have:
                continue
            t0 = time.time()
            try:
                q = generate_question(spec, dom, level, None,
                                      [x["topic"] for x in data["items"] if x["domain"] == dom])
                opts = [q["correct"], *q["distractors"]]
                random.Random(f"{dom}{level}").shuffle(opts)
                review = self_check(q["prompt"], q["code"], opts, opts.index(q["correct"]))
            except (llm.LLMError, ValueError) as exc:
                print(f"{dom} L{level}: ошибка — {exc}", flush=True)
                continue
            data["items"].append({"domain": dom, "level": level, "specialization": spec, **q, "model": settings.llm_model,
                                  "review": {**review, "options": opts}})
            out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
            print(f"{dom} L{level}: «{q['topic']}» — {review['verdict']} ({time.time() - t0:.0f} с)", flush=True)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "build-demo":
    build_demo(tuple(int(x) for x in sys.argv[2].split(",")) if len(sys.argv) > 2 else (2, 3, 4))
