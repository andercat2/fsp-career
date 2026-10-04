"""Валидация механики тестирования (адаптивный тест на модели IRT + параметрические семейства заданий).

Эталонной разметки на хакатоне нет, поэтому используется симуляция с известной «истиной»: у каждого синтетического
кандидата задан истинный уровень θ и доменные способности, ответы генерируются моделью IRT. Это стандартный способ
проверки адаптивных тестов (Monte-Carlo CAT simulation). Проверяем:

  1. Точность оценки уровня: смещение, RMSE, корреляция θ̂ с θ.
  2. Точность категоризации: решение «грейд подтверждён» и итоговый грейд против истинного; сравнение с самооценкой.
  3. Согласованность: повторное прохождение (другие задания) даёт тот же грейд? — доля совпадений, взвешенная каппа.
  4. Дискриминативность заданий: индекс D и точечно-бисериальная корреляция в калибровочном исследовании.
  5. Устойчивость к распространению заданий: экспозиция, пересечение наборов, атака «утечкой» против фиксированного
     теста и банка без параметрических вариантов, обнаружение утечки по дрейфу решаемости и по person-fit.
  6. Устойчивость к ошибкам априорной калибровки и эффект онлайн-калибровки.
  7. Сопоставимость: нет систематического сдвига оценки между языками кода.

Запуск: python -m validation.cat_validation
"""
from __future__ import annotations

import math
import random
import statistics as st
import time
from collections import Counter, defaultdict

import numpy as np

from app.seed.synthetic import SPEC_DIST, default_params, generate_population, simulate_assessment, simulate_cat
from app.services.reference.taxonomy import (
    GRADE_CODES,
    GRADE_INDEX,
    SPECIALIZATIONS,
    THETA_CUTS,
    grade_center,
    resolve_blueprint,
    theta_to_grade,
)
from app.services.testing import irt
from app.services.testing.bank import BY_DOMAIN, REGISTRY
from app.services.testing.cat import CatConfig, ItemState, band_for_decision
from app.services.testing.irt import calibrate_b
from validation.common import cohen_kappa, gini, point_biserial, r3, save_report, weighted_kappa

CFG = CatConfig()


def _grade_idx(g: str | None) -> int:
    return -1 if g is None else GRADE_INDEX[g]


# --------------------------------------------------------------------------- 1–3. точность и согласованность

def recovery_and_classification(pop, params, rng) -> tuple[dict, dict]:
    errs, thetas, hats, lens, ses = [], [], [], [], []
    decisions = Counter()
    correct_dec = 0
    false_confirm = false_reject = n_below = n_above = 0
    exposures: Counter = Counter()
    admin_log = []  # (family, correct, theta_true)
    by_lang = defaultdict(list)
    for c in pop:
        state, res = simulate_cat(c.domain_theta, c.spec, c.lang, c.claimed_grade, rng, params, CFG)
        lo, _ = band_for_decision(c.claimed_grade)
        truth = c.theta >= lo
        confirmed = res["decision"] != "not_confirmed"
        decisions[res["decision"]] += 1
        correct_dec += confirmed == truth
        if not truth:
            n_below += 1
            false_confirm += confirmed
        else:
            n_above += 1
            false_reject += not confirmed
        errs.append(res["theta"] - c.theta)
        thetas.append(c.theta)
        hats.append(res["theta"])
        lens.append(res["n_items"])
        ses.append(res["se"])
        if c.spec == "backend":
            by_lang[c.lang].append(res["theta"] - c.theta)
        for x in state.answered:
            exposures[x.family_id] += 1
            admin_log.append((x.family_id, int(x.correct), c.theta))
    rec = {
        "n": len(pop),
        "bias": r3(np.mean(errs)), "rmse": r3(math.sqrt(np.mean(np.square(errs)))),
        "pearson_r": r3(np.corrcoef(thetas, hats)[0, 1]), "mean_se": r3(np.mean(ses)),
        "test_length": {"mean": r3(np.mean(lens)), "p10": int(np.percentile(lens, 10)), "p90": int(np.percentile(lens, 90)),
                        "min": int(min(lens)), "max": int(max(lens))},
        "est_duration_min": r3(np.mean(lens) * np.mean([f.time_limit for f in REGISTRY.values()]) * 0.55 / 60),
        "decision": {
            "accuracy": r3(correct_dec / len(pop)),
            "false_confirm_rate": r3(false_confirm / max(1, n_below)),
            "false_reject_rate": r3(false_reject / max(1, n_above)),
            "distribution": dict(decisions),
        },
        "bias_by_language_backend": {k: {"n": len(v), "bias": r3(np.mean(v)), "rmse": r3(math.sqrt(np.mean(np.square(v))))}
                                     for k, v in sorted(by_lang.items())},
        "scatter_sample": [[r3(t), r3(h)] for t, h in list(zip(thetas, hats, strict=True))[:400]],
    }
    return rec, {"exposures": exposures, "admin_log": admin_log}


def grade_accuracy_and_retest(pop, params, rng) -> dict:
    true_g, test_g, claim_g, retest_g, th1, th2 = [], [], [], [], [], []
    no_grade = 0
    confusion = np.zeros((4, 5), dtype=int)  # строки — истинный грейд, столбцы — присвоенный (+ «нет»)
    for c in pop:
        simulate_assessment(c, rng, params)
        tg = theta_to_grade(c.theta)
        g1 = c.grade
        seen = {x.family_id for _, s, _ in c.sessions for x in s.answered}
        # повторное прохождение: новые задания (система исключает семейства, виденные за 180 дней)
        c2 = type(c)(**{**c.__dict__, "attempts": [], "sessions": [], "grade": None, "theta_hat": None, "se": None,
                        "domain_scores": {}})
        _assess_with_exclusion(c2, rng, params, seen)
        true_g.append(GRADE_INDEX[tg])
        claim_g.append(GRADE_INDEX[c.claimed_grade])
        test_g.append(_grade_idx(g1))
        retest_g.append(_grade_idx(c2.grade))
        confusion[GRADE_INDEX[tg], (GRADE_INDEX[g1] if g1 else 4)] += 1
        if g1 is None:
            no_grade += 1
        if c.theta_hat is not None and c2.theta_hat is not None:
            th1.append(c.theta_hat)
            th2.append(c2.theta_hat)
    n = len(pop)
    exact = sum(a == b for a, b in zip(true_g, test_g, strict=True)) / n
    adj = sum(b >= 0 and abs(a - b) <= 1 for a, b in zip(true_g, test_g, strict=True)) / n
    claim_exact = sum(a == b for a, b in zip(true_g, claim_g, strict=True)) / n
    over_test = sum(b > a for a, b in zip(true_g, test_g, strict=True) if b >= 0) / n
    over_claim = sum(b > a for a, b in zip(true_g, claim_g, strict=True)) / n
    both = [(a, b) for a, b in zip(test_g, retest_g, strict=True) if a >= 0 and b >= 0]
    agree = sum(a == b for a, b in both) / len(both)
    return {
        "n": n,
        "grade_exact_accuracy": r3(exact), "grade_within_one": r3(adj),
        "self_declared_exact_accuracy": r3(claim_exact),
        "overgrading_rate_test": r3(over_test), "overgrading_rate_self_declared": r3(over_claim),
        "no_category_rate": r3(no_grade / n),
        "confusion_true_vs_assigned": {"rows": GRADE_CODES, "cols": GRADE_CODES + ["нет"], "matrix": confusion.tolist()},
        "retest": {
            "n_pairs": len(both), "grade_agreement": r3(agree),
            "cohen_kappa": r3(cohen_kappa([a for a, _ in both], [b for _, b in both])),
            "weighted_kappa": r3(weighted_kappa([a for a, _ in both], [b for _, b in both], 4)),
            "theta_test_retest_r": r3(np.corrcoef(th1, th2)[0, 1]),
        },
    }


def _assess_with_exclusion(c, rng, params, exclude: set[str]) -> None:
    """Как simulate_assessment, но с исключением ранее виденных семейств (политика пересдачи в продукте)."""
    target = c.claimed_grade
    tried: set[str] = set()
    seen = set(exclude)
    best = None
    best_res = None
    for _ in range(4):
        if target in tried:
            break
        tried.add(target)
        state, res = simulate_cat(c.domain_theta, c.spec, c.lang, target, rng, params, CFG, exclude=seen)
        seen |= {x.family_id for x in state.answered}
        if res["decision"] in ("confirmed", "confirmed_strong"):
            if best is None or GRADE_INDEX[target] > GRADE_INDEX[best]:
                best, best_res = target, res
            if res["decision"] == "confirmed_strong" and res.get("next_grade"):
                target = res["next_grade"]
                continue
            break
        if best is not None or not res.get("suggested_grade"):
            break
        target = res["suggested_grade"]
    if best:
        c.grade, c.theta_hat = best, best_res["theta"]


# --------------------------------------------------------------------------- 4. дискриминативность

def item_discrimination(rng, n_per_item: int = 300) -> dict:
    """Калибровочное исследование: каждое семейство решают 300 случайных кандидатов θ ~ N(0,1) (без адаптивности).
    Индекс D = доля верных у верхних 27% − у нижних 27%; r_pb — корреляция верности с уровнем."""
    ds, rpbs = [], []
    by_kind = defaultdict(list)
    for fam in REGISTRY.values():
        th = [rng.gauss(0, 1) for _ in range(n_per_item)]
        u = [int(rng.random() < float(irt.prob(t + rng.gauss(0, 0.35), fam.a, fam.b, fam.c))) for t in th]
        order = np.argsort(th)
        k = int(0.27 * n_per_item)
        low = np.mean([u[i] for i in order[:k]])
        high = np.mean([u[i] for i in order[-k:]])
        d = high - low
        r = point_biserial(u, th)
        ds.append(d)
        rpbs.append(r)
        by_kind["parametric" if fam.parametric else "static"].append(d)
    return {
        "families": len(ds), "median_D": r3(np.median(ds)), "share_D_ge_0_3": r3(np.mean(np.array(ds) >= 0.3)),
        "share_D_lt_0_2": r3(np.mean(np.array(ds) < 0.2)), "median_rpb": r3(np.median(rpbs)),
        "median_D_parametric": r3(np.median(by_kind["parametric"])), "median_D_static": r3(np.median(by_kind["static"])),
        "note": "D ≥ 0.3 — хорошее задание по классической теории тестов; D < 0.2 — кандидат на доработку.",
    }


def test_information_curves() -> dict:
    """Информационная функция теста по специализациям: сколько информации может дать банк на каждом уровне θ
    при составе по блюпринту (20 заданий). Чем выше — тем точнее измерение на этом уровне."""
    grid = np.linspace(-3, 3, 25)
    out = {}
    for sp in SPECIALIZATIONS:
        bp = resolve_blueprint(sp["code"], sp["languages"][0])
        info = []
        for t in grid:
            total = 0.0
            for dom, w in bp.items():
                k = max(1, round(w * 20))
                vals = sorted((float(irt.information(t, f.a, f.b, f.c)) for f in BY_DOMAIN[dom]), reverse=True)[:k]
                total += sum(vals)
            info.append(r3(total))
        out[sp["code"]] = info
    return {"theta": [r3(t) for t in grid], "info": out, "se_from_info": "SE(θ) ≈ 1/√I(θ)"}


# --------------------------------------------------------------------------- 5. утечки

def exposure_stats(exposures: Counter, n_tests: int) -> dict:
    rates = [exposures.get(f, 0) / n_tests for f in REGISTRY]
    used = sum(1 for f in REGISTRY if exposures.get(f, 0) > 0)
    return {
        "bank_families": len(REGISTRY), "used_families": used, "used_share": r3(used / len(REGISTRY)),
        "max_exposure_rate": r3(max(rates)), "p95_exposure_rate": r3(np.percentile(rates, 95)),
        "gini": r3(gini(rates)),
        "top10": [[f, r3(n / n_tests)] for f, n in exposures.most_common(10)],
    }


def overlap_stats(params, rng, n_pairs: int = 300) -> dict:
    """Пересечение наборов заданий у двух кандидатов одной специализации и одного уровня.
    Семейства могут совпасть, но конкретный вариант параметрического семейства у каждого свой."""
    fam_overlap, identical_overlap = [], []
    for _ in range(n_pairs):
        spec = random.choices([s for s, _ in SPEC_DIST], [p for _, p in SPEC_DIST])[0]
        lang = rng.choice(next(s for s in SPECIALIZATIONS if s["code"] == spec)["languages"])
        bp = resolve_blueprint(spec, lang)
        th = rng.gauss(0, 1)
        dt = {d: th + rng.gauss(0, 0.35) for d in bp}
        g = theta_to_grade(th)
        s1, _ = simulate_cat(dt, spec, lang, g, rng, params, CFG)
        s2, _ = simulate_cat(dt, spec, lang, g, rng, params, CFG)
        a = {x.family_id for x in s1.answered}
        b = {x.family_id for x in s2.answered}
        inter = a & b
        fam_overlap.append(len(inter) / max(1, min(len(a), len(b))))
        identical_overlap.append(sum(1 for f in inter if not REGISTRY[f].parametric) / max(1, min(len(a), len(b))))
    return {"pairs": n_pairs, "mean_family_overlap": r3(np.mean(fam_overlap)),
            "mean_identical_question_overlap": r3(np.mean(identical_overlap)),
            "note": "Сопоставимые кандидаты (одинаковый уровень и специализация) — худший случай для пересечения."}


def _fixed_form(spec: str, lang: str, size: int = 20) -> list:
    """Базовая линия: единый фиксированный тест из статичных заданий средней трудности (как у типичных площадок)."""
    bp = resolve_blueprint(spec, lang)
    items = []
    for dom, w in sorted(bp.items(), key=lambda kv: -kv[1]):
        k = max(1, round(w * size))
        pool = sorted((f for f in BY_DOMAIN[dom] if not f.parametric), key=lambda f: abs(f.b))
        items += pool[:k]
    return items[:size]


def leak_attack(params, rng, ks=(5, 25, 100), attackers_per_spec: int = 45) -> dict:
    """Атака «слитой базой»: нечестный кандидат знает всё, что видели K предыдущих кандидатов его специализации
    (чат, форум). Сравниваем три системы на ОДНИХ И ТЕХ ЖЕ нечестных кандидатах (заявляют грейд на ступень выше):
      • наша (адаптивный тест + параметрические варианты + детектор чужого варианта);
      • тот же адаптивный тест на банке только из статичных заданий;
      • фиксированный тест из 20 статичных заданий (как у типичных площадок).
    Метрики: завышение — доля подтверждений грейда выше истинного; обнаружение — доля помеченных сессий."""
    from app.services.testing.integrity import build_index

    collision = build_index()
    static_only = {fid: ItemState(st.a, st.b, st.c, "retired" if REGISTRY[fid].parametric else "active")
                   for fid, st in params.items()}
    systems = {"ours": params, "static_bank": static_only}
    res: dict = {name: {} for name in (*systems, "fixed_form")}
    undetected: dict = {name: {} for name in (*systems, "fixed_form")}
    flags: dict = {name: {} for name in systems}
    honest_flag: dict = {}
    for sp in SPECIALIZATIONS:
        spec = sp["code"]
        lang = sp["languages"][0]
        bp = resolve_blueprint(spec, lang)
        attackers = []
        for _ in range(attackers_per_spec):
            th = max(-2.4, min(1.6, rng.gauss(-0.4, 0.8)))  # чаще списывают слабые кандидаты
            attackers.append((th, {d: th + rng.gauss(0, 0.35) for d in bp}))
        for name, p in systems.items():
            seen_lists = []
            for _ in range(max(ks)):  # поток честных кандидатов, чьи задания «утекают»
                th = rng.gauss(0, 1)
                state, _ = simulate_cat({d: th + rng.gauss(0, 0.35) for d in bp}, spec, lang, theta_to_grade(th), rng, p, CFG)
                seen_lists.append({x.family_id for x in state.answered})
            for k in (0, *ks):
                db = set().union(*seen_lists[:k]) if k else None
                infl = fl = und = 0
                for th, dt in attackers:
                    claim = GRADE_CODES[min(3, GRADE_INDEX[theta_to_grade(th)] + 1)]
                    _, r = simulate_cat(dt, spec, lang, claim, rng, p, CFG, cheat_known=db, collision=collision)
                    inflated = r["decision"] != "not_confirmed" and claim != theta_to_grade(th)
                    flagged = bool(r["integrity"]["flags"])
                    infl += inflated
                    fl += flagged
                    und += inflated and not flagged
                res[name].setdefault(k, []).append(infl / len(attackers))
                undetected[name].setdefault(k, []).append(und / len(attackers))
                if k == 0:
                    honest_flag.setdefault(name, []).append(fl / len(attackers))
                else:
                    flags[name].setdefault(k, []).append(fl / len(attackers))
        # фиксированная форма: порог подтверждения — нижний квартиль доли верных у честных кандидатов уровня
        form = _fixed_form(spec, lang)
        thr = {}
        for g in GRADE_CODES:
            scores = []
            for _ in range(150):
                th = rng.uniform(*[(-2.6, -1.0), (-1.0, 0.0), (0.0, 1.0), (1.0, 2.6)][GRADE_INDEX[g]])
                scores.append(np.mean([rng.random() < float(irt.prob(th + rng.gauss(0, 0.35), f.a, f.b, f.c)) for f in form]))
            thr[g] = float(np.percentile(scores, 25))
        for k in (0, *ks):
            infl = 0
            for th, dt in attackers:
                claim = GRADE_CODES[min(3, GRADE_INDEX[theta_to_grade(th)] + 1)]
                probs = [0.98 if k else float(irt.prob(dt.get(f.domain, th), f.a, f.b, f.c)) for f in form]
                sc = np.mean([rng.random() < q for q in probs])
                infl += sc >= thr[claim] and claim != theta_to_grade(th)
            res["fixed_form"].setdefault(k, []).append(infl / len(attackers))
            undetected["fixed_form"].setdefault(k, []).append(infl / len(attackers))
    out = {name: {str(k): r3(np.mean(v)) for k, v in d.items()} for name, d in res.items()}
    return {
        "attack_model": "Нечестный кандидат знает все задания, показанные K предыдущим кандидатам его специализации. "
                        "Статичное задание из базы решается с P=0.98; у параметрического другой вариант — шаблон даёт "
                        "+15% к вероятности, а в половине нерешённых случаев вводится слитый ответ чужого варианта.",
        "leak_sizes_K": list(ks), "attackers": attackers_per_spec * len(SPECIALIZATIONS),
        "inflation_rate": out,
        "undetected_inflation_rate": {name: {str(k): r3(np.mean(v)) for k, v in d.items()} for name, d in undetected.items()},
        "detection_rate": {name: {str(k): r3(np.mean(v)) for k, v in d.items()} for name, d in flags.items()},
        "honest_flag_rate": {name: r3(np.mean(v)) for name, v in honest_flag.items()},
        "detectable_families": len(collision),
        "note": "K = 0 — честное прохождение тех же кандидатов (базовый уровень завышения из-за погрешности измерения). "
                "Незамеченное завышение — грейд завышен, а сессия не помечена детекторами (помеченные сессии "
                "направляются на повторный тест под наблюдением).",
    }


def drift_detection(params, rng, n_takers: int = 1800, cheat_share: float = 0.2, n_leaked: int = 12) -> dict:
    """Онлайн-обнаружение утечки статичных заданий по дрейфу решаемости (одна специализация — худший случай
    концентрации показов). Утекли 12 самых часто показываемых статичных семейств, их знают 20% кандидатов.
    Для каждого семейства z = (верных − ожидаемо по модели) / √Σp(1−p) при ≥ 30 показах."""
    spec, lang = "backend", "python"
    bp = resolve_blueprint(spec, lang)
    warm = Counter()
    for _ in range(300):
        th = rng.gauss(0, 1)
        state, _ = simulate_cat({d: th + rng.gauss(0, 0.35) for d in bp}, spec, lang, theta_to_grade(th), rng, params, CFG)
        warm.update(x.family_id for x in state.answered if not REGISTRY[x.family_id].parametric)
    leaked = {f for f, _ in warm.most_common(n_leaked)}
    obs, exp_, var, cnt = Counter(), Counter(), Counter(), Counter()
    checkpoints = {}
    for i in range(1, n_takers + 1):
        cheat = rng.random() < cheat_share
        th = rng.gauss(-0.3 if cheat else 0.0, 1)
        dt = {d: th + rng.gauss(0, 0.35) for d in bp}
        state, res = simulate_cat(dt, spec, lang, theta_to_grade(th), rng, params, CFG, cheat_known=leaked if cheat else None)
        for x in state.answered:
            p = float(irt.prob(res["theta"], x.a, x.b, x.c))
            obs[x.family_id] += x.correct
            exp_[x.family_id] += p
            var[x.family_id] += p * (1 - p)
            cnt[x.family_id] += 1
        if i % 300 == 0:
            z = {f: (obs[f] - exp_[f]) / math.sqrt(var[f]) for f in cnt if cnt[f] >= 30 and var[f] > 0}
            clean = [f for f in z if f not in leaked]
            checkpoints[i] = {
                str(thr): {"tpr": r3(sum(z.get(f, 0) > thr for f in leaked) / len(leaked)),
                           "fpr": r3(sum(z[f] > thr for f in clean) / max(1, len(clean)))}
                for thr in (2.5, 3.0)
            }
    return {"specialization": f"{spec}/{lang}", "leaked_static_families": n_leaked, "cheater_share": cheat_share,
            "takers": n_takers, "checkpoints": checkpoints,
            "note": "TPR — доля утекших семейств, выведенных из ротации; FPR — доля чистых, помеченных ошибочно. "
                    "В продукте порог z > 3; помеченное семейство заменяется, результаты кандидатов не аннулируются."}


# --------------------------------------------------------------------------- 6. ошибки калибровки

def misspecification(rng, n: int = 900) -> dict:
    """Истинные параметры заданий отличаются от экспертных априорных (b ± 0.4, a × e^N(0,0.25)).
    Сравниваем: CAT на априорных параметрах → после онлайн-калибровки трудности → «оракул» (истинные параметры)."""
    prior = default_params()
    true = {fid: ItemState(st.a * math.exp(rng.gauss(0, 0.25)), st.b + rng.gauss(0, 0.4), st.c) for fid, st in prior.items()}

    def population(k, seed):
        return generate_population(k, seed=seed, inflation_rate=0.0)

    def run(pop, used_params):
        exact = 0
        errs = []
        log = []
        for c in pop:
            # ответы порождаются ИСТИННЫМИ параметрами: подменяем способности через «эквивалентную» модель
            state, res = _cat_true_responses(c, used_params, true, rng)
            errs.append(res["theta"] - c.theta)
            exact += theta_to_grade(res["theta"]) == theta_to_grade(c.theta)
            log += [(x.family_id, x.correct, res["theta"]) for x in state.answered]
        return r3(exact / len(pop)), r3(math.sqrt(np.mean(np.square(errs)))), log

    pop_a = population(n, 501)
    acc_prior, rmse_prior, log = run(pop_a, prior)
    calibrated = dict(prior)
    by_f = defaultdict(list)
    for f, u, th in log:
        by_f[f].append((u, th))
    b_err_prior, b_err_cal = [], []
    for f, rows in by_f.items():
        if len(rows) < 30:
            continue
        st0 = prior[f]
        best_b = calibrate_b([u for u, _ in rows], [th for _, th in rows], st0.a, st0.c)
        calibrated[f] = ItemState(st0.a, best_b, st0.c)
        b_err_prior.append(st0.b - true[f].b)
        b_err_cal.append(best_b - true[f].b)
    pop_b = population(n, 502)
    acc_cal, rmse_cal, _ = run(pop_b, calibrated)
    acc_oracle, rmse_oracle, _ = run(pop_b, true)
    acc_prior_b, rmse_prior_b, _ = run(pop_b, prior)
    return {
        "perturbation": "b_true = b_prior + N(0, 0.4), a_true = a_prior · exp(N(0, 0.25))",
        "calibrated_families": len(b_err_cal),
        "b_rmse_prior": r3(math.sqrt(np.mean(np.square(b_err_prior)))),
        "b_rmse_after_calibration": r3(math.sqrt(np.mean(np.square(b_err_cal)))),
        "grade_accuracy": {"prior_params": acc_prior_b, "after_online_calibration": acc_cal, "oracle_true_params": acc_oracle},
        "theta_rmse": {"prior_params": rmse_prior_b, "after_online_calibration": rmse_cal, "oracle_true_params": rmse_oracle},
        "note": "Калибровка — фиксированные θ̂ из рабочих сессий и MLE трудности (реализовано: /admin/items/calibrate).",
    }


def _cat_true_responses(c, used_params, true_params, rng):
    from app.services.testing.cat import AnsweredItem, CatState, decide, select_next, should_stop

    bp = resolve_blueprint(c.spec, c.lang)
    state = CatState(bp, theta_to_grade(c.theta), c.lang)
    while not should_stop(state, CFG):
        fam = select_next(state, used_params, rng, CFG)
        if fam is None:
            break
        t = true_params[fam.id]
        th = c.domain_theta.get(fam.domain, c.theta)
        u = rng.random() < float(irt.prob(th, t.a, t.b, t.c))
        st = used_params[fam.id]
        state.answered.append(AnsweredItem(fam.id, fam.domain, st.a, st.b, st.c, bool(u), True, None, fam.time_limit, fam.level))
    return state, decide(state, CFG)


# --------------------------------------------------------------------------- запуск

def main(n: int = 1500, seed: int = 11) -> dict:
    t0 = time.time()
    rng = random.Random(seed)
    random.seed(seed)
    params = default_params()
    pop = generate_population(n, seed=seed)
    recovery, logs = recovery_and_classification(pop, params, rng)
    pop2 = generate_population(n, seed=seed + 1)
    grades = grade_accuracy_and_retest(pop2, params, rng)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "config": {"min_items": CFG.min_items, "max_items": CFG.max_items, "se_stop": CFG.se_stop,
                   "confidence": CFG.confidence, "randomesque": CFG.randomesque, "max_exposure": CFG.max_exposure,
                   "theta_cuts": THETA_CUTS, "grade_centers": {g: grade_center(g) for g in GRADE_CODES},
                   "population": n, "inflated_claims_share": 0.35},
        "recovery": recovery,
        "grades": grades,
        "discrimination": item_discrimination(rng),
        "exposure": exposure_stats(logs["exposures"], n),
        "overlap": overlap_stats(params, rng),
        "leak_attack": leak_attack(params, rng),
        "drift_detection": drift_detection(params, rng),
        "misspecification": misspecification(rng),
        "information": test_information_curves(),
    }
    report["runtime_sec"] = round(time.time() - t0, 1)
    save_report("cat_validation", report)
    return report


if __name__ == "__main__":
    import json

    rep = main()
    short = {k: v for k, v in rep.items() if k not in ("information",)}
    short["recovery"] = {k: v for k, v in rep["recovery"].items() if k != "scatter_sample"}
    print(json.dumps(short, ensure_ascii=False, indent=1))
