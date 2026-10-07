"""Сервис тестирования: допуск к тестам и кулдауны, жизненный цикл сессии CAT, присвоение категории,
онлайн-статистика заданий (экспозиция, дрейф решаемости → пометка скомпрометированных заданий)."""
from __future__ import annotations

import math
import random
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import utcnow
from app.core.security import derive_seed
from app.models import CandidateProfile, GradeHistory, ItemStat, TestResponse, TestSession
from app.services.notify import notify
from app.services.reference.taxonomy import (
    DOMAINS,
    GRADE_CODES,
    GRADE_INDEX,
    GRADE_NAMES,
    SPEC_NAMES,
    grade_center,
    resolve_blueprint,
)
from app.services.resumes import target_for
from app.services.testing import integrity, irt
from app.services.testing.bank import REGISTRY, check_answer
from app.services.testing.cat import AnsweredItem, CatConfig, CatState, ItemState, decide, select_next, should_stop

CFG = CatConfig()
SESSION_TTL_HOURS = 3
TIME_GRACE_SEC = 15
DRIFT_Z_FLAG = 3.0
DRIFT_MIN_EXPOSURES = 30
PRETEST_RATE = 0.12
PRETEST_PROMOTE_N = 40

# Прокторинг: снимок экрана / печать / копирование текста задания — «страйк». Первый — предупреждение,
# второй — тест завершается досрочно, нарушение фиксируется, оценка уровня понижается на PROCTOR_PENALTY логита.
PROCTOR_STRIKE_KINDS = {"screenshot", "print", "copy"}
PROCTOR_MAX_STRIKES = 2
PROCTOR_PENALTY = 0.5  # ≈ половина ширины грейда на шкале θ
PROCTOR_DEDUPE_SEC = 3  # одно действие, пойманное двумя детекторами (клавиша + потеря фокуса), — один страйк
PROCTOR_MAX_EVENTS = 200
VIOLATION_NAMES = {"screenshot": "снимок экрана", "print": "печать или сохранение страницы",
                   "copy": "копирование текста задания"}


def effective_time_limit(base: int, b: float) -> int:
    """Время на ответ зависит от формата задания (base: выбор — 90 с, код и вычисления — 120–240 с) и от его
    трудности b по IRT: лёгкое — до −20 %, трудное — до +35 %. Округляется до 5 секунд."""
    factor = min(1.35, max(0.8, 1 + 0.15 * b))
    return max(45, int(round(base * factor / 5) * 5))


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

def _current_grade(prof) -> str | None:
    """prof — профиль (основное резюме) или CandidateResume: поля опроса и категории у них одинаковые."""
    if prof.grade and prof.grade_specialization == prof.specialization:
        return prof.grade
    return None


def eligibility(db: Session, cand: CandidateProfile, resume_id: int | None = None) -> dict:
    """Допуск к тесту по резюме (категории): ограничения частоты действуют для каждой категории отдельно,
    одновременно может идти только один тест."""
    now = utcnow()
    prof = target_for(cand, resume_id)
    if not prof.specialization or not prof.survey_completed_at:
        return {"ready": False, "reason": "Сначала пройдите опрос по отрасли и специализации", "grades": [],
                "in_progress": None, "resume_id": resume_id or 0}
    active = db.scalar(select(TestSession).where(TestSession.candidate_id == cand.id, TestSession.status == "in_progress"))
    if active and active.started_at < now - timedelta(hours=SESSION_TTL_HOURS):
        active.status = "abandoned"
        active.finished_at = now
        db.commit()
        active = None
    sessions = list(db.scalars(select(TestSession).where(
        TestSession.candidate_id == cand.id, TestSession.specialization == prof.specialization,
        TestSession.status.in_(["completed", "abandoned"])).order_by(TestSession.started_at.desc())))
    current = _current_grade(prof)
    # «Уверенный» результат открывает следующий уровень без ожидания, но тест не начинается сам: кандидат запускает
    # его, когда будет готов (срока нет). Это одна попытка — после неё действуют обычные ограничения частоты.
    strong_next = None
    for s in sessions:
        if s.status == "completed" and s.result and s.result.get("decision") == "confirmed_strong":
            nxt = s.result.get("next_grade")
            used = any(x.target_grade == nxt and x.started_at > s.started_at for x in sessions)
            if nxt and not used and (current is None or GRADE_INDEX[nxt] > GRADE_INDEX[current]):
                strong_next = nxt
            break
    grades = []
    for g in GRADE_CODES:
        last = next((s for s in sessions if s.target_grade == g), None)
        item = {"grade": g, "name": GRADE_NAMES[g], "allowed": True, "reason": None, "available_from": None,
                "recommended": g == (prof.claimed_grade or "junior") and not current}
        retake_from = last.started_at + timedelta(days=settings.same_level_retake_days) if last else None
        if current and GRADE_INDEX[g] < GRADE_INDEX[current]:
            item.update(allowed=False, reason="Ниже текущего грейда: грейд не понижается")
        elif retake_from and retake_from > now and not (strong_next == g):
            item.update(allowed=False, reason=f"Повторная попытка этого уровня — через {settings.same_level_retake_days} "
                                              "дней после предыдущей", available_from=retake_from.isoformat())
        elif current and GRADE_INDEX[g] > GRADE_INDEX[current] and strong_next != g:
            changed = prof.grade_changed_at or prof.grade_assigned_at
            if changed and changed + timedelta(days=settings.grade_change_cooldown_days) > now:
                avail = changed + timedelta(days=settings.grade_change_cooldown_days)
                item.update(allowed=False, reason=f"Смена грейда возможна не чаще раза в "
                                                  f"{settings.grade_change_cooldown_days} дней",
                            available_from=avail.isoformat())
        if strong_next == g:
            item.update(recommended=True, reason="Вы уверенно прошли предыдущий уровень — тест доступен без ожидания, "
                                                 "когда будете готовы")
        grades.append(item)
    return {"ready": True, "reason": None, "grades": grades, "current_grade": current,
            "in_progress": active.token if active else None, "resume_id": resume_id or 0,
            "specialization": prof.specialization, "language": prof.primary_language,
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
                                        r.payload.get("time_limit", fam.time_limit if fam else None),
                                        fam.level if fam else 3,
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
    b = st.b if st else fam.b
    resp = TestResponse(
        session_id=sess.id, seq=seq, family_id=fam.id, domain=fam.domain, variant_seed=f"{seed:016x}", scored=scored,
        payload={
            "prompt": r.prompt, "kind": r.kind, "options": r.options, "code": r.code, "code_lang": r.code_lang,
            "placeholder": r.placeholder, "time_limit": effective_time_limit(fam.time_limit, b), "domain": fam.domain,
            "domain_name": DOMAINS.get(fam.domain, fam.domain), "topic": fam.topic,
            "irt": {"a": st.a if st else fam.a, "b": b, "c": st.c if st else fam.c},
        },
        answer_key={"key": r.key, "tolerance": r.tolerance, "accepted": r.accepted, "norm": r.norm,
                    "explanation": r.explanation},
    )
    db.add(resp)
    sess.responses.append(resp)
    return resp


def start_session(db: Session, cand: CandidateProfile, grade: str, resume_id: int | None = None) -> TestSession:
    if grade not in GRADE_CODES:
        raise HTTPException(422, "Неизвестный грейд")
    el = eligibility(db, cand, resume_id)
    if not el["ready"]:
        raise HTTPException(409, el["reason"])
    if el["in_progress"]:
        sess = db.scalar(select(TestSession).where(TestSession.token == el["in_progress"]))
        return sess
    g = next(x for x in el["grades"] if x["grade"] == grade)
    if not g["allowed"]:
        raise HTTPException(409, g["reason"])
    prof = target_for(cand, resume_id)
    sess = TestSession(
        token=secrets.token_urlsafe(16), candidate_id=cand.id, resume_id=resume_id or None,
        specialization=prof.specialization, language=prof.primary_language, target_grade=grade,
        blueprint=resolve_blueprint(prof.specialization, prof.primary_language),
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
        "resume_id": sess.resume_id or 0, "specialization": sess.specialization, "specialization_name": SPEC_NAMES.get(sess.specialization),
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
    if sess.status == "in_progress":
        pr = sess.proctoring or {}
        base["proctoring"] = {"strikes": pr.get("strikes", 0), "max_strikes": PROCTOR_MAX_STRIKES,
                              "penalty": PROCTOR_PENALTY}
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
    pr = sess.proctoring or {}
    r["proctoring"] = {"strikes": pr.get("strikes", 0), "away_count": pr.get("away_count", 0),
                       "violation": pr.get("violation"), "violation_name": VIOLATION_NAMES.get(pr.get("violation")),
                       "penalty": r.pop("penalty", 0.0), "terminated": bool(pr.get("terminated"))}
    r.pop("raw_theta", None)
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


def record_proctoring(db: Session, sess: TestSession, kind: str, method: str | None = None,
                      away_ms: int | None = None) -> dict:
    """Событие прокторинга от клиента. Правило «двух страйков» применяется на сервере (клиенту не доверяем
    подсчёт): 1-й снимок экрана → предупреждение, 2-й → досрочное завершение со штрафом к оценке."""
    if sess.status != "in_progress":
        raise HTTPException(409, "Сессия тестирования уже завершена")
    now = utcnow()
    pr = dict(sess.proctoring or {})
    strikes = int(pr.get("strikes", 0))
    resp = current_response(sess)
    ev = {"kind": kind, "at": now.isoformat(), "seq": resp.seq if resp else None}
    if method:
        ev["method"] = method
    action = "logged"
    if kind in PROCTOR_STRIKE_KINDS:
        last = pr.get("last_strike_at")
        if last and (now - datetime.fromisoformat(last)).total_seconds() < PROCTOR_DEDUPE_SEC:
            ev["duplicate"] = True
            action = "duplicate"
        else:
            strikes += 1
            pr["last_strike_at"] = now.isoformat()
            action = "warn" if strikes < PROCTOR_MAX_STRIKES else "terminate"
    else:  # уход со вкладки / потеря фокуса — мягкий сигнал: учитывается, но тест не прерывает
        pr["away_count"] = int(pr.get("away_count", 0)) + 1
        pr["away_ms"] = int(pr.get("away_ms", 0)) + int(away_ms or 0)
        if away_ms:
            ev["away_ms"] = int(away_ms)
    pr["strikes"] = strikes
    pr["events"] = (list(pr.get("events", [])) + [ev])[-PROCTOR_MAX_EVENTS:]
    if action == "terminate":
        pr["violation"], pr["terminated"] = kind, True
    sess.proctoring = pr
    if action == "terminate":
        if resp is not None:  # задание, на котором зафиксировано нарушение, засчитывается как неверное
            resp.answered_at = now
            resp.time_ms = int((now - resp.presented_at).total_seconds() * 1000)
            resp.is_correct = False
            resp.payload = {**resp.payload, "terminated": True}
        _finalize(db, sess, _state_from_session(sess), penalty=PROCTOR_PENALTY)
    db.commit()
    return {"action": action, "strikes": strikes, "max_strikes": PROCTOR_MAX_STRIKES,
            "view": question_view(sess, current_response(sess))}


def accept_suggested(db: Session, sess: TestSession) -> dict:
    """Принять грейд ниже заявленного по результатам этого же теста — без повторного прохождения. Доступно, если
    тест с вероятностью ≥ lower_accept_prob показал уровень не ниже этого грейда (точность на валидации — 99.8%)."""
    from app.services.matching.profile import recompute_candidate  # локальный импорт: избегаем цикла модулей

    r = dict(sess.result or {})
    if sess.status != "completed" or r.get("decision") != "not_confirmed" or not r.get("suggested_assignable"):
        raise HTTPException(409, "По этому тесту нельзя присвоить грейд ниже — пройдите тест на этот уровень")
    if r.get("accepted_suggested") or r.get("review_required"):
        raise HTTPException(409, "Решение по этому тесту уже принято")
    cand = db.get(CandidateProfile, sess.candidate_id)
    target = next((x for x in cand.resumes if x.id == sess.resume_id), None) if sess.resume_id else cand
    if target is None:
        raise HTTPException(409, "Резюме этого теста удалено")
    grade = r["suggested_grade"]
    current = _current_grade(target)
    if current and GRADE_INDEX[current] >= GRADE_INDEX[grade]:
        raise HTTPException(409, "У вас уже есть грейд не ниже предложенного")
    db.add(GradeHistory(candidate_id=cand.id, resume_id=sess.resume_id, specialization=sess.specialization,
                        old_grade=current, new_grade=grade, theta=r["theta"], session_id=sess.id))
    if current is not None:
        target.grade_changed_at = utcnow()
    target.grade, target.grade_specialization = grade, sess.specialization
    target.grade_assigned_at = target.grade_assigned_at or utcnow()
    clear_unconfirmed(target)
    # доменные оценки в профиле — относительно принятого грейда (в сессии они посчитаны для заявленного)
    center = grade_center(grade)
    domains = {d: {**v, "score": round(1 / (1 + math.exp(-1.3 * (v["theta"] - center))), 3)}
               for d, v in r["domains"].items()}
    target.grade_theta, target.grade_se, target.domain_scores = r["theta"], r["se"], domains
    sess.result = {**r, "accepted_suggested": True, "assigned_grade": grade, "kept_grade": None}
    recompute_candidate(db, cand)
    notify(db, cand.user_id, "test_result", f"Грейд {GRADE_NAMES[grade]} присвоен по результатам теста",
           "Категория видна работодателям. Следующий уровень можно подтвердить отдельным тестом.", "/candidate/grade")
    db.commit()
    return question_view(sess, None)


def set_unconfirmed(target, grade: str, result: dict, at=None) -> None:
    """Тест не подтвердил заявленный грейд, а подтверждённого нет: резюме остаётся в выдаче со статусом
    «не подтверждён» и ниже подтверждённых. θ, погрешность и доменные оценки — измеренные этим тестом."""
    target.unconfirmed_grade, target.unconfirmed_theta, target.unconfirmed_se = grade, result["theta"], result["se"]
    target.unconfirmed_at = at or utcnow()
    target.domain_scores = result.get("domains") or {}


def clear_unconfirmed(target) -> None:
    target.unconfirmed_grade = target.unconfirmed_theta = target.unconfirmed_se = target.unconfirmed_at = None


def sync_unconfirmed(db: Session) -> int:
    """Статус неподтверждённого грейда из истории тестов — для данных, созданных до появления статуса (идемпотентно):
    резюме без подтверждённого грейда получает результат последнего завершённого теста своей специализации, если
    тест грейд не подтвердил и не ушёл на перепроверку."""
    latest: dict[tuple, TestSession] = {}
    for s in db.scalars(select(TestSession).where(TestSession.status == "completed").order_by(TestSession.finished_at)):
        latest[(s.candidate_id, s.resume_id or 0, s.specialization)] = s
    changed = 0
    for (cand_id, resume_id, spec), s in latest.items():
        r = s.result or {}
        if r.get("decision") != "not_confirmed" or r.get("review_required") or r.get("accepted_suggested"):
            continue
        cand = db.get(CandidateProfile, cand_id)
        target = (next((x for x in cand.resumes if x.id == resume_id), None) if resume_id else cand) if cand else None
        if target is None or target.specialization != spec or _current_grade(target) or target.grade:
            continue
        if target.unconfirmed_grade == s.target_grade and target.unconfirmed_at:
            continue
        set_unconfirmed(target, s.target_grade, r, s.finished_at)
        changed += 1
    if changed:
        db.commit()
    return changed


def abandon(db: Session, sess: TestSession) -> None:
    if sess.status == "in_progress":
        sess.status = "abandoned"
        sess.finished_at = utcnow()
        db.commit()


def _finalize(db: Session, sess: TestSession, state: CatState, penalty: float = 0.0) -> None:
    from app.services.matching.profile import recompute_candidate  # локальный импорт: избегаем цикла модулей

    result = decide(state, CFG, penalty)
    sess.status = "completed"
    sess.finished_at = utcnow()
    # в сессии — измеренная θ (для калибровки и дрейфа заданий), в результате — итоговая, со штрафом
    measured = result.get("raw_theta", result["theta"])
    sess.theta, sess.se = measured, result["se"]
    flagged = _update_item_stats(db, sess, measured)
    if flagged:
        result["flagged_items"] = flagged
    cand = db.get(CandidateProfile, sess.candidate_id)
    # категория пишется в резюме, по которому шёл тест; основное резюме — сам профиль
    target = next((r for r in cand.resumes if r.id == sess.resume_id), None) if sess.resume_id else cand
    current = _current_grade(target) if target is not None else None
    decision = result["decision"]
    assigned = None
    # Ответы «чужого варианта» — признак списанных ответов: грейд не меняется автоматически до перепроверки
    review = "foreign_variant_answers" in result["integrity"]["flags"]
    result["review_required"] = review
    if decision in ("confirmed", "confirmed_strong") and not review and target is not None:
        if current is None or GRADE_INDEX[sess.target_grade] > GRADE_INDEX[current]:
            assigned = sess.target_grade
            db.add(GradeHistory(candidate_id=cand.id, resume_id=sess.resume_id, specialization=sess.specialization,
                                old_grade=current, new_grade=assigned, theta=result["theta"], session_id=sess.id))
            if current is not None:
                target.grade_changed_at = utcnow()
            target.grade = assigned
            target.grade_specialization = sess.specialization
            target.grade_assigned_at = target.grade_assigned_at or utcnow()
            clear_unconfirmed(target)
        if current is None or GRADE_INDEX[sess.target_grade] >= GRADE_INDEX[current]:
            # обновляем «свежесть» подтверждённого уровня и доменные оценки
            target.grade_theta, target.grade_se = result["theta"], result["se"]
            target.domain_scores = result["domains"]
    elif decision == "not_confirmed" and not review and target is not None and current is None:
        set_unconfirmed(target, sess.target_grade, result)
    result["assigned_grade"] = assigned
    result["kept_grade"] = current if assigned is None else None
    sess.result = result
    recompute_candidate(db, cand)
    if penalty:
        pr = sess.proctoring or {}
        notify(db, cand.user_id, "test_violation", "Тест завершён досрочно: зафиксировано нарушение",
               f"Повторно зафиксировано действие «{VIOLATION_NAMES.get(pr.get('violation'), 'нарушение')}». Результат "
               "засчитан с пониженной оценкой уровня.", "/candidate/grade")
        return
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
            "token": s.token, "resume_id": s.resume_id or 0, "specialization": s.specialization,
            "specialization_name": SPEC_NAMES.get(s.specialization),
            "target_grade": s.target_grade, "target_grade_name": GRADE_NAMES[s.target_grade], "status": s.status,
            "started_at": s.started_at, "finished_at": s.finished_at, "n_items": s.n_items, "n_correct": s.n_correct,
            "decision": (s.result or {}).get("decision"),
            "theta": (s.result or {}).get("theta", s.theta) if s.status == "completed" else None,
            "percentile": (s.result or {}).get("percentile"),
            "violation": (s.proctoring or {}).get("violation"),
        })
    return out
