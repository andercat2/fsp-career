"""Сервис тестирования: допуск к тестам и кулдауны, жизненный цикл сессии CAT, присвоение категории,
онлайн-статистика заданий (экспозиция, дрейф решаемости → пометка скомпрометированных заданий)."""
from __future__ import annotations

import math
import random
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import utcnow
from app.core.security import derive_seed
from app.models import CandidateProfile, GradeHistory, ItemStat, TestResponse, TestSession
from app.services.notify import notify
from app.services.reference.taxonomy import DOMAINS, GRADE_CODES, GRADE_INDEX, GRADE_NAMES, SPEC_NAMES, resolve_blueprint
from app.services.testing import integrity, irt
from app.services.testing.bank import REGISTRY, check_answer
from app.services.testing.cat import AnsweredItem, CatConfig, CatState, ItemState, decide, select_next, should_stop

CFG = CatConfig()
STRONG_UPGRADE_WINDOW_DAYS = 7
SESSION_TTL_HOURS = 3
TIME_GRACE_SEC = 15
DRIFT_Z_FLAG = 3.0
DRIFT_MIN_EXPOSURES = 30
PRETEST_RATE = 0.12
PRETEST_PROMOTE_N = 40


# ---------------------------------------------------------------- статистика заданий

def sync_item_stats(db: Session) -> None:
    """Создаёт строки статистики для новых семейств банка (вызывается при старте приложения)."""
    existing = set(db.scalars(select(ItemStat.family_id)))
    for fam in REGISTRY.values():
        if fam.id not in existing:
            db.add(ItemStat(family_id=fam.id, status="pretest" if fam.pretest else "active", a=fam.a, b=fam.b, c=fam.c))
    db.commit()


def load_params(db: Session) -> dict[str, ItemState]:
    total = db.scalar(select(func.count()).select_from(TestSession).where(TestSession.status == "completed")) or 0
    out = {}
    for st in db.scalars(select(ItemStat)):
        out[st.family_id] = ItemState(st.a, st.b, st.c, st.status, st.exposures / max(total, 20))
    return out


def _update_item_stats(db: Session, sess: TestSession, theta: float) -> list[str]:
    """Сравниваем наблюдаемую решаемость с предсказанной моделью. Систематически «слишком лёгкое» задание
    (z > 3 при ≥ 30 показах) — признак утечки: семейство выводится из ротации."""
    flagged = []
    for r in sess.responses:
        if r.answered_at is None or not r.scored:
            continue
        st = db.get(ItemStat, r.family_id)
        if st is None:
            continue
        p = float(irt.prob(theta, st.a, st.b, st.c))
        st.exposures += 1
        st.correct += int(bool(r.is_correct))
        st.expected_correct += p
        st.expected_var += p * (1 - p)
        if st.expected_var > 0:
            st.drift_z = (st.correct - st.expected_correct) / math.sqrt(st.expected_var)
        if st.status == "active" and st.exposures >= DRIFT_MIN_EXPOSURES and st.drift_z > DRIFT_Z_FLAG:
            st.status = "flagged"
            flagged.append(st.family_id)
    return flagged


def calibrate_pretest(db: Session) -> list[dict]:
    """Онлайн-калибровка пилотных заданий (метод фиксированных θ): по ответам кандидатов с известной итоговой θ
    методом максимального правдоподобия оцениваем трудность b и переводим задание в рабочий банк."""
    out = []
    for st in db.scalars(select(ItemStat).where(ItemStat.status == "pretest")):
        rows = db.execute(
            select(TestResponse.is_correct, TestSession.theta)
            .join(TestSession, TestSession.id == TestResponse.session_id)
            .where(TestResponse.family_id == st.family_id, TestResponse.scored.is_(False),
                   TestSession.status == "completed", TestResponse.answered_at.is_not(None))
        ).all()
        if len(rows) < PRETEST_PROMOTE_N:
            out.append({"family_id": st.family_id, "n": len(rows), "promoted": False})
            continue
        best_b = irt.calibrate_b([bool(u) for u, _ in rows], [th for _, th in rows], st.a, st.c)
        st.b = best_b
        st.status = "active"
        out.append({"family_id": st.family_id, "n": len(rows), "promoted": True, "b": best_b})
    db.commit()
    return out


# ---------------------------------------------------------------- допуск и кулдауны

def _current_grade(cand: CandidateProfile) -> str | None:
    if cand.grade and cand.grade_specialization == cand.specialization:
        return cand.grade
    return None


def eligibility(db: Session, cand: CandidateProfile) -> dict:
    now = utcnow()
    if not cand.specialization or not cand.survey_completed_at:
        return {"ready": False, "reason": "Сначала пройдите опрос по отрасли и специализации", "grades": [],
                "in_progress": None}
    active = db.scalar(select(TestSession).where(TestSession.candidate_id == cand.id, TestSession.status == "in_progress"))
    if active and active.started_at < now - timedelta(hours=SESSION_TTL_HOURS):
        active.status = "abandoned"
        active.finished_at = now
        db.commit()
        active = None
    sessions = list(db.scalars(select(TestSession).where(
        TestSession.candidate_id == cand.id, TestSession.specialization == cand.specialization,
        TestSession.status.in_(["completed", "abandoned"])).order_by(TestSession.started_at.desc())))
    current = _current_grade(cand)
    strong_next = None
    for s in sessions:
        if s.status == "completed" and s.result and s.result.get("decision") == "confirmed_strong":
            if s.finished_at and s.finished_at > now - timedelta(days=STRONG_UPGRADE_WINDOW_DAYS):
                strong_next = s.result.get("next_grade")
            break
    grades = []
    for g in GRADE_CODES:
        last = next((s for s in sessions if s.target_grade == g), None)
        item = {"grade": g, "name": GRADE_NAMES[g], "allowed": True, "reason": None, "available_from": None,
                "recommended": g == (cand.claimed_grade or "junior") and not current}
        retake_from = last.started_at + timedelta(days=settings.same_level_retake_days) if last else None
        if current and GRADE_INDEX[g] < GRADE_INDEX[current]:
            item.update(allowed=False, reason="Ниже текущего грейда: грейд не понижается")
        elif retake_from and retake_from > now and not (strong_next == g):
            item.update(allowed=False, reason=f"Повторная попытка этого уровня — через {settings.same_level_retake_days} "
                                              "дней после предыдущей", available_from=retake_from.isoformat())
        elif current and GRADE_INDEX[g] > GRADE_INDEX[current] and strong_next != g:
            changed = cand.grade_changed_at or cand.grade_assigned_at
            if changed and changed + timedelta(days=settings.grade_change_cooldown_days) > now:
                avail = changed + timedelta(days=settings.grade_change_cooldown_days)
                item.update(allowed=False, reason=f"Смена грейда возможна не чаще раза в "
                                                  f"{settings.grade_change_cooldown_days} дней",
                            available_from=avail.isoformat())
        if strong_next == g:
            item.update(recommended=True, reason="Вы уверенно прошли предыдущий уровень — можно сразу попробовать этот")
        grades.append(item)
    return {"ready": True, "reason": None, "grades": grades, "current_grade": current,
            "in_progress": active.token if active else None,
            "specialization": cand.specialization, "language": cand.primary_language,
            "cooldown_days": settings.grade_change_cooldown_days}


# ---------------------------------------------------------------- сессия

def _state_from_session(sess: TestSession) -> CatState:
    st = CatState(sess.blueprint, sess.target_grade, sess.language)
    for r in sess.responses:
        if r.answered_at is None:
            continue
        fam = REGISTRY.get(r.family_id)
        p = r.payload.get("irt", {})
        st.answered.append(AnsweredItem(r.family_id, r.domain, p.get("a", fam.a if fam else 1.0),
                                        p.get("b", fam.b if fam else 0.0), p.get("c", fam.c if fam else 0.0),
                                        bool(r.is_correct), r.scored, r.time_ms,
                                        fam.time_limit if fam else None, fam.level if fam else 3,
                                        bool(r.payload.get("foreign_answer"))))
    return st


def _recent_family_ids(db: Session, cand_id: int, exclude_session: int | None = None) -> set[str]:
    """Семейства, которые кандидат уже видел за 180 дней: при пересдаче он получит другие задания."""
    since = utcnow() - timedelta(days=180)
    q = (select(TestResponse.family_id).join(TestSession, TestSession.id == TestResponse.session_id)
         .where(TestSession.candidate_id == cand_id, TestSession.started_at >= since))
    if exclude_session:
        q = q.where(TestSession.id != exclude_session)
    return set(db.scalars(q))


def _present_next(db: Session, sess: TestSession, state: CatState, rng: random.Random) -> TestResponse | None:
    params = load_params(db)
    exclude = _recent_family_ids(db, sess.candidate_id, sess.id) | {r.family_id for r in sess.responses}
    n_scored = len(state.scored)
    fam = None
    scored = True
    if n_scored >= 4 and rng.random() < PRETEST_RATE:
        pre = [f for f in REGISTRY.values() if params.get(f.id) and params[f.id].status == "pretest"
               and f.domain in sess.blueprint and f.id not in exclude]
        if pre:
            fam, scored = rng.choice(pre), False
    if fam is None:
        fam = select_next(state, params, rng, CFG, exclude=exclude)
    if fam is None:
        # банк по блюпринту исчерпан — допускаем ранее виденные кандидатом семейства (варианты всё равно новые)
        fam = select_next(state, params, rng, CFG, exclude={r.family_id for r in sess.responses})
    if fam is None:
        return None
    seq = len(sess.responses) + 1
    seed = derive_seed(sess.token, fam.id, seq)
    r = fam.render(seed, sess.language)
    st = params.get(fam.id)
    resp = TestResponse(
        session_id=sess.id, seq=seq, family_id=fam.id, domain=fam.domain, variant_seed=f"{seed:016x}", scored=scored,
        payload={
            "prompt": r.prompt, "kind": r.kind, "options": r.options, "code": r.code, "code_lang": r.code_lang,
            "placeholder": r.placeholder, "time_limit": fam.time_limit, "domain": fam.domain,
            "domain_name": DOMAINS.get(fam.domain, fam.domain), "topic": fam.topic,
            "irt": {"a": st.a if st else fam.a, "b": st.b if st else fam.b, "c": st.c if st else fam.c},
        },
        answer_key={"key": r.key, "tolerance": r.tolerance, "accepted": r.accepted, "norm": r.norm,
                    "explanation": r.explanation},
    )
    db.add(resp)
    sess.responses.append(resp)
    return resp


def start_session(db: Session, cand: CandidateProfile, grade: str) -> TestSession:
    if grade not in GRADE_CODES:
        raise HTTPException(422, "Неизвестный грейд")
    el = eligibility(db, cand)
    if not el["ready"]:
        raise HTTPException(409, el["reason"])
    if el["in_progress"]:
        sess = db.scalar(select(TestSession).where(TestSession.token == el["in_progress"]))
        return sess
    g = next(x for x in el["grades"] if x["grade"] == grade)
    if not g["allowed"]:
        raise HTTPException(409, g["reason"])
    sess = TestSession(
        token=secrets.token_urlsafe(16), candidate_id=cand.id, specialization=cand.specialization,
        language=cand.primary_language, target_grade=grade,
        blueprint=resolve_blueprint(cand.specialization, cand.primary_language),
    )
    db.add(sess)
    db.flush()
    rng = random.Random(derive_seed(sess.token, "rng"))
    _present_next(db, sess, CatState(sess.blueprint, grade, sess.language), rng)
    db.commit()
    return sess


def current_response(sess: TestSession) -> TestResponse | None:
    pending = [r for r in sess.responses if r.answered_at is None]
    return pending[-1] if pending else None


def question_view(sess: TestSession, resp: TestResponse | None) -> dict:
    """То, что видит кандидат: без ключа ответа и параметров IRT."""
    base = {
        "token": sess.token, "status": sess.status, "target_grade": sess.target_grade,
        "specialization": sess.specialization, "specialization_name": SPEC_NAMES.get(sess.specialization),
        "answered": len([r for r in sess.responses if r.answered_at is not None]),
        "max_items": CFG.max_items, "min_items": CFG.min_items, "blueprint": {
            k: {"weight": v, "name": DOMAINS.get(k, k)} for k, v in sess.blueprint.items()},
    }
    if resp is not None:
        p = dict(resp.payload)
        p.pop("irt", None)
        elapsed = (utcnow() - resp.presented_at).total_seconds()
        base["question"] = {"id": resp.id, "seq": resp.seq, **p,
                            "time_left": max(0, int(p["time_limit"] - elapsed))}
    if sess.status == "completed":
        base["result"] = public_result(sess)
    return base


def public_result(sess: TestSession) -> dict | None:
    if not sess.result:
        return None
    r = dict(sess.result)
    r.pop("integrity", None)
    r["domains"] = {k: {**v, "name": DOMAINS.get(k, k)} for k, v in r.get("domains", {}).items()}
    r["target_grade"] = sess.target_grade
    r["target_grade_name"] = GRADE_NAMES[sess.target_grade]
    if r.get("suggested_grade"):
        r["suggested_grade_name"] = GRADE_NAMES[r["suggested_grade"]]
    if r.get("next_grade"):
        r["next_grade_name"] = GRADE_NAMES[r["next_grade"]]
    r["review"] = [
        {"seq": x.seq, "topic": x.payload.get("topic"), "domain": x.payload.get("domain_name"),
         "correct": x.is_correct, "scored": x.scored, "explanation": x.answer_key.get("explanation") or None}
        for x in sess.responses if x.answered_at is not None
    ]
    return r


def submit_answer(db: Session, sess: TestSession, response_id: int, answer) -> dict:
    if sess.status != "in_progress":
        raise HTTPException(409, "Сессия тестирования уже завершена")
    resp = current_response(sess)
    if resp is None or resp.id != response_id:
        raise HTTPException(409, "Ответ относится не к текущему заданию")
    now = utcnow()
    elapsed = (now - resp.presented_at).total_seconds()
    resp.answer = answer
    resp.answered_at = now
    resp.time_ms = int(elapsed * 1000)
    timed_out = elapsed > resp.payload["time_limit"] + TIME_GRACE_SEC
    k = resp.answer_key
    resp.is_correct = (not timed_out) and check_answer(resp.payload["kind"], k["key"], answer,
                                                       tolerance=k.get("tolerance", 0), accepted=k.get("accepted"),
                                                       norm=k.get("norm", "tokens"))
    if not resp.is_correct and integrity.detectable(resp.family_id) is not None:
        _check_foreign_answer(db, resp, answer)
    state = _state_from_session(sess)
    theta, se = state.estimate()
    resp.theta_after, resp.se_after = theta, se
    sess.theta, sess.se = theta, se
    sess.n_items = len(state.scored)
    sess.n_correct = sum(1 for *_, u in state.scored if u)
    rng = random.Random(derive_seed(sess.token, "rng", resp.seq))
    if should_stop(state, CFG) or _present_next(db, sess, state, rng) is None:
        _finalize(db, sess, state)
    db.commit()
    return question_view(sess, current_response(sess))


def _check_foreign_answer(db: Session, resp: TestResponse, answer) -> None:
    """Неверный ответ совпал с правильным ответом чужого варианта этого семейства → вероятно, списан."""
    kind = resp.payload["kind"]
    mine = integrity.norm_answer(kind, answer)
    own_key = integrity.norm_answer(kind, resp.answer_key.get("key"))
    if not mine or mine == own_key:
        return
    others = db.scalars(select(TestResponse.answer_key).where(
        TestResponse.family_id == resp.family_id, TestResponse.session_id != resp.session_id)
        .order_by(TestResponse.id.desc()).limit(3000))
    if any(integrity.norm_answer(kind, k.get("key")) == mine for k in others if k):
        resp.payload = {**resp.payload, "foreign_answer": True}


def abandon(db: Session, sess: TestSession) -> None:
    if sess.status == "in_progress":
        sess.status = "abandoned"
        sess.finished_at = utcnow()
        db.commit()


def _finalize(db: Session, sess: TestSession, state: CatState) -> None:
    from app.services.matching.profile import recompute_candidate  # локальный импорт: избегаем цикла модулей

    result = decide(state, CFG)
    sess.status = "completed"
    sess.finished_at = utcnow()
    sess.theta, sess.se = result["theta"], result["se"]
    flagged = _update_item_stats(db, sess, result["theta"])
    if flagged:
        result["flagged_items"] = flagged
    cand = db.get(CandidateProfile, sess.candidate_id)
    current = _current_grade(cand)
    decision = result["decision"]
    assigned = None
    # Ответы «чужого варианта» — признак списанных ответов: грейд не меняется автоматически до перепроверки
    review = "foreign_variant_answers" in result["integrity"]["flags"]
    result["review_required"] = review
    if decision in ("confirmed", "confirmed_strong") and not review:
        if current is None or GRADE_INDEX[sess.target_grade] > GRADE_INDEX[current]:
            assigned = sess.target_grade
            db.add(GradeHistory(candidate_id=cand.id, specialization=sess.specialization, old_grade=current,
                                new_grade=assigned, theta=result["theta"], session_id=sess.id))
            if current is not None:
                cand.grade_changed_at = utcnow()
            cand.grade = assigned
            cand.grade_specialization = sess.specialization
            cand.grade_assigned_at = cand.grade_assigned_at or utcnow()
        if current is None or GRADE_INDEX[sess.target_grade] >= GRADE_INDEX[current]:
            # обновляем «свежесть» подтверждённого уровня и доменные оценки
            cand.grade_theta, cand.grade_se = result["theta"], result["se"]
            cand.domain_scores = result["domains"]
    result["assigned_grade"] = assigned
    result["kept_grade"] = current if assigned is None else None
    sess.result = result
    recompute_candidate(db, cand)
    if review:
        notify(db, cand.user_id, "test_review", "Результат теста отправлен на перепроверку",
               "Часть ответов совпала с ответами других вариантов заданий. Пройдите, пожалуйста, тест повторно "
               "в формате под наблюдением — это стандартная процедура.", "/candidate/grade")
        return
    title = {
        "confirmed": f"Грейд {GRADE_NAMES[sess.target_grade]} подтверждён",
        "confirmed_strong": f"Грейд {GRADE_NAMES[sess.target_grade]} подтверждён уверенно",
        "not_confirmed": f"Грейд {GRADE_NAMES[sess.target_grade]} пока не подтверждён",
    }[decision]
    notify(db, cand.user_id, "test_result", title, "Результаты тестирования доступны в разделе «Категория и грейд».",
           "/candidate/grade")


def history(db: Session, cand: CandidateProfile) -> list[dict]:
    sessions = db.scalars(select(TestSession).where(TestSession.candidate_id == cand.id)
                          .order_by(TestSession.started_at.desc()))
    out = []
    for s in sessions:
        out.append({
            "token": s.token, "specialization": s.specialization, "specialization_name": SPEC_NAMES.get(s.specialization),
            "target_grade": s.target_grade, "target_grade_name": GRADE_NAMES[s.target_grade], "status": s.status,
            "started_at": s.started_at, "finished_at": s.finished_at, "n_items": s.n_items, "n_correct": s.n_correct,
            "decision": (s.result or {}).get("decision"), "theta": s.theta if s.status == "completed" else None,
            "percentile": (s.result or {}).get("percentile"),
        })
    return out
