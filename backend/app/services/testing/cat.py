"""Адаптивное тестирование (CAT) — «чистое» ядро без зависимостей от БД, используется и сервисом, и симуляцией.

Как выбирается следующее задание:
1. Балансировка содержания: домен с наибольшим отставанием от доли в блюпринте специализации.
2. Внутри домена — семейства с максимальной информацией Фишера в текущей оценке θ.
3. Randomesque-контроль экспозиции: случайный выбор среди top-k по информации + пропуск «перегретых»
   семейств (доля показов выше порога). Так разные кандидаты получают разные наборы заданий.
Каждое семейство дополнительно рендерится в уникальный вариант (см. bank/core.py).

Остановка: не меньше min_items; затем — как только SE ≤ порога или решение по обеим границам заявленного
грейда принято с уверенностью ≥ confidence; не больше max_items.
Решение: грейд подтверждён, если апостериорная вероятность P(θ ≥ нижней границы грейда) ≥ confirm_prob.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from app.services.reference.taxonomy import GRADE_CODES, GRADE_INDEX, grade_band, grade_center, theta_to_grade
from app.services.testing import irt
from app.services.testing.bank import BY_DOMAIN, ItemFamily

INTERN_FLOOR = -2.0  # ниже этого уровня категория «Стажёр» не присваивается — нужна подготовка


@dataclass
class CatConfig:
    """Значения подобраны симуляцией (validation/cat_validation.py): баланс точности и длины теста ~20 минут."""
    min_items: int = 12
    max_items: int = 24
    se_stop: float = 0.28
    confidence: float = 0.92
    randomesque: int = 4
    max_exposure: float = 0.30
    confirm_prob: float = 0.60  # грейд подтверждается, если P(θ ≥ нижней границы) ≥ 0.6
    parametric_bonus: float = 1.0  # множитель информации для параметрических семейств (предпочтение при равенстве)
    strong_margin: float = 0.80  # P(θ ≥ верхней границы), при которой предлагается повышение


@dataclass
class ItemState:
    a: float
    b: float
    c: float
    status: str = "active"
    exposure_rate: float = 0.0


@dataclass
class AnsweredItem:
    family_id: str
    domain: str
    a: float
    b: float
    c: float
    correct: bool
    scored: bool = True
    time_ms: int | None = None
    time_limit: int | None = None
    level: int = 3
    foreign: bool = False  # ответ совпал с ключом чужого варианта того же семейства (см. integrity.py)


@dataclass
class CatState:
    blueprint: dict[str, float]
    target_grade: str
    language: str | None
    answered: list[AnsweredItem] = field(default_factory=list)

    @property
    def scored(self) -> list[tuple[float, float, float, bool]]:
        return [(x.a, x.b, x.c, x.correct) for x in self.answered if x.scored]

    def estimate(self) -> tuple[float, float]:
        return irt.eap(self.scored)


def band_for_decision(grade: str) -> tuple[float, float]:
    lo, hi = grade_band(grade)
    return (INTERN_FLOOR if math.isinf(lo) else lo), hi


def select_next(state: CatState, params: dict[str, ItemState], rng: random.Random, cfg: CatConfig,
                exclude: set[str] | None = None) -> ItemFamily | None:
    used = {x.family_id for x in state.answered} | (exclude or set())
    n = len([x for x in state.answered if x.scored])
    theta_hat, _ = state.estimate()
    # До накопления ответов ориентируемся на центр заявленного грейда (только для выбора, не для оценки!)
    start = grade_center(state.target_grade)
    w = min(n, 3) / 3
    theta_sel = (1 - w) * start + w * theta_hat

    counts: dict[str, int] = {}
    for x in state.answered:
        counts[x.domain] = counts.get(x.domain, 0) + 1

    def eligible(dom: str) -> list[ItemFamily]:
        out = []
        for fam in BY_DOMAIN.get(dom, []):
            st = params.get(fam.id)
            if fam.id in used or (st and st.status not in ("active",)):
                continue
            out.append(fam)
        return out

    domains = sorted(state.blueprint, key=lambda d: (-(state.blueprint[d] * (n + 1) - counts.get(d, 0)), rng.random()))
    for dom in domains:
        pool = eligible(dom)
        if not pool:
            continue
        cool = [f for f in pool if not params.get(f.id) or params[f.id].exposure_rate <= cfg.max_exposure]
        pool = cool or pool

        def info(f: ItemFamily) -> float:
            st = params.get(f.id)
            a, b, c = (st.a, st.b, st.c) if st else (f.a, f.b, f.c)
            bonus = cfg.parametric_bonus if f.parametric else 1.0
            return float(irt.information(theta_sel, a, b, c)) * bonus

        ranked = sorted(pool, key=info, reverse=True)
        return rng.choice(ranked[: cfg.randomesque])
    return None


def should_stop(state: CatState, cfg: CatConfig) -> bool:
    scored = state.scored
    n = len(scored)
    if n >= cfg.max_items:
        return True
    if n < cfg.min_items:
        return False
    _, se = irt.eap(scored)
    if se <= cfg.se_stop:
        return True
    lo, hi = band_for_decision(state.target_grade)
    p_lo = irt.posterior_prob_above(scored, lo)
    lo_sure = p_lo >= cfg.confidence or p_lo <= 1 - cfg.confidence
    if math.isinf(hi):
        return lo_sure
    p_hi = irt.posterior_prob_above(scored, hi)
    hi_sure = p_hi >= cfg.confidence or p_hi <= 1 - cfg.confidence
    return lo_sure and hi_sure


def domain_scores(state: CatState, theta: float) -> dict[str, dict]:
    """Оценка по доменам: EAP по ответам домена с prior в общей θ (сжатие к общей оценке при малом n).
    score — вероятность решить типичное задание уровня заявленного грейда."""
    out: dict[str, dict] = {}
    target_b = grade_center(state.target_grade)
    by_dom: dict[str, list[AnsweredItem]] = {}
    for x in state.answered:
        if x.scored:
            by_dom.setdefault(x.domain, []).append(x)
    for dom, items in by_dom.items():
        resp = [(x.a, x.b, x.c, x.correct) for x in items]
        ll = irt.log_likelihood_grid(resp) - 0.5 * ((irt.GRID - theta) / 0.8) ** 2
        ll -= ll.max()
        wts = [math.exp(v) for v in ll]
        s = sum(wts)
        th = sum(g * w_ for g, w_ in zip(irt.GRID, wts, strict=True)) / s
        score = 1 / (1 + math.exp(-1.3 * (th - target_b)))
        out[dom] = {"n": len(items), "correct": sum(x.correct for x in items), "theta": round(th, 3),
                    "score": round(score, 3)}
    return out


def integrity_flags(state: CatState, theta: float) -> dict:
    """Признаки нечестного прохождения: несогласованный паттерн ответов (person-fit), подозрительно быстрые верные
    ответы на трудные задания и ответы «чужого варианта». Не влияют на грейд автоматически — сессия помечается
    для проверки (повторный тест под наблюдением)."""
    lz = irt.person_fit_lz(theta, state.scored)
    fast = 0
    for x in state.answered:
        if x.scored and x.correct and x.level >= 4 and x.time_ms is not None and x.time_limit:
            if x.time_ms < 0.08 * x.time_limit * 1000:
                fast += 1
    foreign = sum(1 for x in state.answered if x.foreign)
    flags = []
    if lz is not None and lz < -2.0:
        flags.append("aberrant_pattern")
    if fast >= 2:
        flags.append("too_fast_on_hard_items")
    if foreign >= 2:
        flags.append("foreign_variant_answers")
    return {"lz": None if lz is None else round(lz, 3), "fast_hard_correct": fast, "foreign_answers": foreign,
            "flags": flags}


def decide(state: CatState, cfg: CatConfig) -> dict:
    theta, se = state.estimate()
    lo, hi = band_for_decision(state.target_grade)
    scored = state.scored
    p_lo = irt.posterior_prob_above(scored, lo)
    p_hi = 0.0 if math.isinf(hi) else irt.posterior_prob_above(scored, hi)
    idx = GRADE_INDEX[state.target_grade]
    # Порог 0.6, а не 0.5: ошибка «завысили грейд» дороже для работодателя, чем «предложили пересдать уровнем ниже»
    if p_lo >= cfg.confirm_prob:
        decision = "confirmed"
        if not math.isinf(hi) and p_hi >= cfg.strong_margin and idx < len(GRADE_CODES) - 1:
            decision = "confirmed_strong"
    else:
        decision = "not_confirmed"
    suggested = theta_to_grade(theta) if theta >= INTERN_FLOOR else None
    if decision == "not_confirmed" and suggested and GRADE_INDEX[suggested] >= idx:
        suggested = GRADE_CODES[idx - 1] if idx > 0 else None
    # процентиль относительно «рынка» N(0,1) — понятная работодателю шкала
    percentile = round(100 * 0.5 * (1 + math.erf(theta / math.sqrt(2))), 1)
    return {
        "decision": decision,
        "theta": round(theta, 3),
        "se": round(se, 3),
        "p_above_lower": round(p_lo, 3),
        "p_above_upper": round(p_hi, 3),
        "band": [None if math.isinf(lo) else lo, None if math.isinf(hi) else hi],
        "suggested_grade": suggested,
        "next_grade": GRADE_CODES[idx + 1] if decision == "confirmed_strong" else None,
        "percentile": percentile,
        "n_items": len(scored),
        "n_correct": sum(1 for *_, u in scored if u),
        "domains": domain_scores(state, theta),
        "integrity": integrity_flags(state, theta),
    }
