"""Валидация механики подбора: доля релевантных кандидатов в топе выдачи на наборе пар «потребность — кандидат».

Готовой разметки нет, поэтому релевантность пары задаётся из ЛАТЕНТНОЙ истины синтетической популяции (истинные
специализация, грейд и навыки — их не видит ни одна из систем), а системы ранжирования видят только наблюдаемые
данные: резюме (≈35% кандидатов завышают грейд и добавляют модные навыки), результаты теста, ФСП, условия.

Сравниваем:
  keyword          — полнотекстовый поиск по резюме (TF-IDF), как на универсальных площадках;
  filters          — классические фильтры по самоописанию: специализация + заявленный грейд + зарплата + город,
                     ранжирование по покрытию заявленных навыков;
  ours             — категории по тесту + ранжирование платформы (структурированная потребность);
  ours_nlp         — то же, но потребность получена NLP-разбором текста вакансии (сквозной сценарий);
  абляции ours     — без ФСП, без подтверждения навыков тестом, грейд из самоописания вместо теста.

Метрики: Precision@10 (доля релевантных, метка ≥ 2), nDCG@10 (по меткам 0–3), MRR, доля нерелевантных (метка 0)
в топ-10 и доля «завысивших себя» неподходящих кандидатов в топ-10.

Запуск: python -m validation.matching_validation
"""
from __future__ import annotations

import math
import random
import time

import numpy as np

from app.core.db import utcnow
from app.models import CandidateProfile
from app.seed.fsp_data import _achievement
from app.seed.synthetic import (
    BASE_SALARY,
    CITY_DIST,
    SPEC_DIST,
    SPEC_SALARY,
    SynthCandidate,
    default_params,
    generate_population,
    simulate_assessment,
)
from app.services.fsp.scoring import fsp_score
from app.services.matching.profile import W_FSP, W_TEST, test_position, verified_skills
from app.services.matching.ranking import RELATED_SPECS, Need, score_candidates
from app.services.nlp.vacancy_parser import parse_need
from app.services.reference.skills import SKILL_BY_ID, skills_for_spec
from app.services.reference.taxonomy import GRADE_CODES, GRADE_INDEX, SPEC_BY_CODE, grade_center
from validation.common import mrr, ndcg_at_k, precision_at_k, r3, save_report

K = 10


# --------------------------------------------------------------------------- данные

def _fsp_profile(c: SynthCandidate, rng: random.Random) -> dict | None:
    if c.fsp_quality is None:
        return None
    n = rng.choice([0, 1, 1, 2, 2, 3])
    return {"achievements": [_achievement(rng, c.fsp_quality) for _ in range(n)]}


def to_profile(c: SynthCandidate, rng: random.Random, *, use_test: bool = True, use_fsp: bool = True,
               use_verification: bool = True) -> CandidateProfile:
    if use_test:
        grade, theta, se, domains = c.grade, c.theta_hat, c.se, c.domain_scores
    else:  # категория из самоописания
        grade, theta, se, domains = c.claimed_grade, grade_center(c.claimed_grade), None, {}
    p = CandidateProfile(
        id=c.idx + 1, public_id=f"S{c.idx:04d}", grade=grade, grade_specialization=c.spec if grade else None,
        grade_theta=theta, grade_se=se, domain_scores=(domains or {}) if use_verification else {}, skills=list(c.declared_skills), desired_salary=c.desired_salary,
        work_formats=c.work_formats, city=c.city, relocation=c.relocation, headline=c.headline, about=c.about,
        experience=c.experience, open_to_offers=True, tasks_done=0, privacy={}, specialization=c.spec, primary_language=c.lang,
        claimed_grade=c.claimed_grade, last_active_at=utcnow(),
        fsp_profile=getattr(c, "_fsp", None) if use_fsp else None,
    )
    p.verified_skills = verified_skills(p) if use_verification else []
    p.fsp_score = fsp_score(p.fsp_profile, p.grade_specialization)
    p.strength = round(W_TEST * test_position(p) + W_FSP * p.fsp_score, 4) if grade else 0.0
    return p


def make_needs(n: int, rng: random.Random) -> list[dict]:
    needs = []
    for i in range(n):
        spec = rng.choices([s for s, _ in SPEC_DIST], [p for _, p in SPEC_DIST])[0]
        g = rng.choices(GRADE_CODES, [0.08, 0.32, 0.4, 0.2])[0]
        grades = [g]
        if rng.random() < 0.35:
            j = GRADE_INDEX[g] + rng.choice([-1, 1])
            if 0 <= j < 4:
                grades = sorted({g, GRADE_CODES[j]}, key=GRADE_INDEX.get)
        pool = [s.id for s in skills_for_spec(spec)]
        core = [s for s in SPEC_BY_CODE[spec]["core_skills"] if s in SKILL_BY_ID]
        must = list(dict.fromkeys(rng.sample(core, min(len(core), rng.randint(2, 3))) + rng.sample(pool, rng.randint(1, 2))))
        nice = [s for s in rng.sample(pool, rng.randint(0, 2)) if s not in must]
        mult = SPEC_SALARY[spec]
        s_from = int(BASE_SALARY[grades[0]] * mult * 0.9 / 5000) * 5000
        s_to = int(BASE_SALARY[grades[-1]] * mult * rng.uniform(1.1, 1.35) / 5000) * 5000
        fmt = rng.choice(["office", "hybrid", "remote", "remote"])
        city = None if fmt == "remote" else rng.choices([c for c, _ in CITY_DIST], [p for _, p in CITY_DIST])[0]
        needs.append({"id": i, "specialization": spec, "grades": grades, "must_skills": must, "nice_skills": nice,
                      "salary_from": s_from, "salary_to": s_to, "work_format": fmt, "city": city})
    for nd in needs:
        nd["text"], nd["title"] = need_text(nd, rng)
    return needs


ROLE = {"backend": "Backend-разработчик", "frontend": "Frontend-разработчик", "fullstack": "Fullstack-разработчик",
        "ml": "Data Scientist", "data_analyst": "Аналитик данных", "devops": "DevOps-инженер", "qa": "QA-инженер"}


def need_text(nd: dict, rng: random.Random) -> tuple[str, str]:
    g = " / ".join({"intern": "стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior"}[x] for x in nd["grades"])
    title = f"{ROLE[nd['specialization']]} ({g})"
    must = ", ".join(SKILL_BY_ID[s].name for s in nd["must_skills"])
    nice = ", ".join(SKILL_BY_ID[s].name for s in nd["nice_skills"])
    fmt = {"office": "офис", "hybrid": "гибридный формат", "remote": "удалённо"}[nd["work_format"]]
    city = f", {nd['city']}" if nd["city"] else ""
    intro = rng.choice(["Ищем в команду", "Приглашаем", "Нужен", "Открыта позиция:"])
    text = (f"{intro} {ROLE[nd['specialization']].lower()} уровня {g}.\nТребования: {must}.\n"
            + (f"Будет плюсом: {nice}.\n" if nice else "")
            + f"Условия: {fmt}{city}, зарплата от {nd['salary_from']:,} до {nd['salary_to']:,} ₽.".replace(",", " "))
    return text, title


def relevance(c: SynthCandidate, nd: dict, proficiency: bool = False) -> int:
    """Истинная релевантность пары по латентным данным (системы их не видят).
    proficiency=False — строгая метрика: важно лишь владение навыком; True — учитывается и уровень владения
    (истинная доменная способность относительно уровня требуемого грейда)."""
    if c.spec == nd["specialization"]:
        sf = 1.0
    else:
        sf = RELATED_SPECS.get(nd["specialization"], {}).get(c.spec, 0.0) * 0.7
    tg = GRADE_INDEX[c.grade_true]
    gi = [GRADE_INDEX[g] for g in nd["grades"]]
    lf = 1.0 if tg in gi else (0.35 if min(abs(tg - x) for x in gi) == 1 else 0.0)
    if proficiency:
        center = grade_center(nd["grades"][0])

        def prof(sid: str) -> float:
            d = SKILL_BY_ID[sid].domains[0] if SKILL_BY_ID[sid].domains else None
            th = c.domain_theta.get(d, c.theta) if d else c.theta
            return 1 / (1 + math.exp(-1.3 * (th - center)))

        cov = sum((s in c.true_skills) * (0.4 + 0.6 * prof(s)) for s in nd["must_skills"]) / len(nd["must_skills"])
    else:
        cov = sum(s in c.true_skills for s in nd["must_skills"]) / len(nd["must_skills"])
    sal = 1.0 if c.desired_salary <= nd["salary_to"] * 1.1 else 0.6
    geo = 1.0 if nd["work_format"] == "remote" or nd["city"] == c.city or c.relocation else 0.5
    r = sf * lf * (0.4 + 0.6 * cov) * sal * geo
    return 3 if r >= 0.7 else 2 if r >= 0.45 else 1 if r >= 0.2 else 0


# --------------------------------------------------------------------------- системы

def rank_keyword(nd, cands: list[SynthCandidate]) -> list[int]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    docs = [nd["title"] + " " + nd["text"]] + [
        f"{c.headline} {c.about} {' '.join(SKILL_BY_ID[s].name for s in c.declared_skills if s in SKILL_BY_ID)} "
        f"{' '.join(e['position'] + ' ' + e['description'] for e in c.experience)}" for c in cands]
    m = TfidfVectorizer(sublinear_tf=True).fit_transform(docs)
    sims = linear_kernel(m[0:1], m[1:]).ravel()
    return [cands[i].idx for i in np.argsort(-sims)]


def rank_filters(nd, cands: list[SynthCandidate]) -> list[int]:
    must = set(nd["must_skills"])

    def ok(c, strict):
        if c.spec != nd["specialization"]:
            return False
        g_ok = c.claimed_grade in nd["grades"] if strict else \
            min(abs(GRADE_INDEX[c.claimed_grade] - GRADE_INDEX[g]) for g in nd["grades"]) <= 1
        sal_ok = c.desired_salary <= nd["salary_to"] * 1.1
        geo_ok = nd["work_format"] == "remote" or nd["city"] == c.city or c.relocation
        return g_ok and sal_ok and geo_ok

    def key(c):
        dec = set(c.declared_skills)
        return (-len(must & dec) / len(must), -c.experience_years)

    strict = sorted((c for c in cands if ok(c, True)), key=key)
    relaxed = sorted((c for c in cands if ok(c, False) and not ok(c, True)), key=key)
    return [c.idx for c in strict + relaxed]


def rank_ours(need: Need, profiles: list[CandidateProfile]) -> list[int]:
    pairs = {(need.specialization, g) for g in need.grades}
    lo = min(GRADE_INDEX[g] for g in need.grades)
    hi = max(GRADE_INDEX[g] for g in need.grades)
    if lo > 0:
        pairs.add((need.specialization, GRADE_CODES[lo - 1]))
    if hi < 3:
        pairs.add((need.specialization, GRADE_CODES[hi + 1]))
    for rel in RELATED_SPECS.get(need.specialization, {}):
        for g in need.grades:
            pairs.add((rel, g))
    pool = [p for p in profiles if p.grade and (p.grade_specialization, p.grade) in pairs]
    return [r["candidate_id"] - 1 for r in score_candidates(need, pool)]


def need_obj(nd: dict) -> Need:
    return Need(specialization=nd["specialization"], grades=nd["grades"], must_skills=nd["must_skills"],
                nice_skills=nd["nice_skills"], salary_from=nd["salary_from"], salary_to=nd["salary_to"],
                work_format=nd["work_format"], city=nd["city"], text=nd["text"], title=nd["title"])


# --------------------------------------------------------------------------- оценка

def evaluate(ranked: list[int], labels: dict[int, int], inflated_bad: set[int]) -> dict:
    rels = [labels[i] for i in ranked]
    ideal = list(labels.values())
    top = ranked[:K]
    return {
        "p10": precision_at_k(rels, K), "ndcg10": ndcg_at_k(rels, K, ideal), "mrr": mrr(rels),
        "irrelevant_in_top10": sum(labels[i] == 0 for i in top) / K,
        "inflated_in_top10": sum(i in inflated_bad for i in top) / K,
        "returned": len(ranked),
    }


def main(n_candidates: int = 900, n_needs: int = 60, seed: int = 101) -> dict:
    t0 = time.time()
    rng = random.Random(seed)
    random.seed(seed)
    params = default_params()
    pop = generate_population(n_candidates, seed=seed)
    for c in pop:
        simulate_assessment(c, rng, params)
        c._fsp = _fsp_profile(c, rng)
    variants = {
        "ours": dict(),
        "ours_no_fsp": dict(use_fsp=False),
        "ours_no_verification": dict(use_verification=False),
        "ours_self_declared_category": dict(use_test=False),
    }
    profiles = {name: [to_profile(c, rng, **kw) for c in pop] for name, kw in variants.items()}
    needs = make_needs(n_needs, rng)
    metrics: dict[str, list[dict]] = {m: [] for m in ["keyword", "filters", *variants, "ours_nlp"]}
    latency = []
    nlp_spec_ok = nlp_grade_ok = 0
    example = None
    metrics_prof: dict[str, list[dict]] = {m: [] for m in metrics}
    for nd in needs:
        labels = {c.idx: relevance(c, nd) for c in pop}
        labels_prof = {c.idx: relevance(c, nd, proficiency=True) for c in pop}
        lo_need = min(GRADE_INDEX[g] for g in nd["grades"])
        inflated_bad = {c.idx for c in pop if c.inflated and GRADE_INDEX[c.grade_true] < lo_need}
        runs = {"keyword": rank_keyword(nd, pop), "filters": rank_filters(nd, pop)}
        need = need_obj(nd)
        for name in variants:
            t = time.perf_counter()
            runs[name] = rank_ours(need, profiles[name])
            if name == "ours":
                latency.append(time.perf_counter() - t)
        parsed = parse_need(nd["text"], nd["title"])
        nlp_spec_ok += parsed["specialization"] == nd["specialization"]
        nlp_grade_ok += set(parsed["grades"]) == set(nd["grades"])
        runs["ours_nlp"] = rank_ours(Need.from_dict(parsed | {"text": nd["text"], "title": nd["title"]}), profiles["ours"])
        for name, ranked in runs.items():
            metrics[name].append(evaluate(ranked, labels, inflated_bad))
            metrics_prof[name].append(evaluate(ranked, labels_prof, inflated_bad))
        if example is None and nd["specialization"] == "backend":
            by_idx = {c.idx: c for c in pop}
            example = {"need": {k: v for k, v in nd.items() if k != "id"},
                       "top5": {name: [{"idx": i, "label": labels[i], "true_grade": by_idx[i].grade_true,
                                        "claimed_grade": by_idx[i].claimed_grade, "inflated": by_idx[i].inflated,
                                        "spec": by_idx[i].spec} for i in runs[name][:5]]
                                for name in ("keyword", "filters", "ours")}}
    summary = {name: {k: r3(np.mean([m[k] for m in ms])) for k in ms[0]} for name, ms in metrics.items()}
    for name, ms in metrics.items():
        summary[name]["needs_with_5plus_relevant_in_top10"] = r3(np.mean([m["p10"] >= 0.5 for m in ms]))
        summary[name]["p10_ci95"] = r3(1.96 * np.std([m["p10"] for m in ms]) / math.sqrt(len(ms)))
    summary_prof = {name: {k: r3(np.mean([m[k] for m in ms])) for k in ("p10", "ndcg10", "mrr", "irrelevant_in_top10")}
                    for name, ms in metrics_prof.items()}
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "setup": {"candidates": n_candidates, "needs": n_needs, "k": K, "inflated_resume_share": 0.35,
                  "relevance": "метка 0–3 из латентных специализации, грейда, навыков, ожиданий по ЗП и географии; "
                               "релевантен — метка ≥ 2",
                  "avg_relevant_per_need": r3(np.mean([sum(relevance(c, nd) >= 2 for c in pop) for nd in needs]))},
        "summary": summary,
        "summary_with_proficiency": summary_prof,
        "nlp_end_to_end": {"specialization_accuracy": r3(nlp_spec_ok / n_needs), "grades_exact": r3(nlp_grade_ok / n_needs)},
        "latency_ms": {"mean": r3(1000 * np.mean(latency)), "p95": r3(1000 * np.percentile(latency, 95)),
                       "pool": "до 900 кандидатов, без кэширования"},
        "example": example,
        "runtime_sec": round(time.time() - t0, 1),
    }
    save_report("matching_validation", report)
    return report


if __name__ == "__main__":
    import json

    rep = main()
    print(json.dumps({k: v for k, v in rep.items() if k != "example"}, ensure_ascii=False, indent=1))
