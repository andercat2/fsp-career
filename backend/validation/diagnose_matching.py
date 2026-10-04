"""Диагностика: почему кандидаты в топ-10 нерелевантны (по латентной истине). Вспомогательный скрипт."""
from __future__ import annotations

import random
from collections import Counter

from app.seed.synthetic import default_params, generate_population, simulate_assessment
from app.services.reference.taxonomy import GRADE_INDEX
from validation import matching_validation as mv


def reasons(c, nd) -> list[str]:
    out = []
    if c.spec != nd["specialization"]:
        out.append("spec")
    tg = GRADE_INDEX[c.grade_true]
    if tg not in [GRADE_INDEX[g] for g in nd["grades"]]:
        out.append("grade")
    cov = sum(s in c.true_skills for s in nd["must_skills"]) / len(nd["must_skills"])
    if cov < 0.5:
        out.append("skills<50%")
    if c.desired_salary > nd["salary_to"] * 1.1:
        out.append("salary")
    if not (nd["work_format"] == "remote" or nd["city"] == c.city or c.relocation):
        out.append("geo")
    return out


def main():
    rng = random.Random(101)
    random.seed(101)
    params = default_params()
    pop = generate_population(900, seed=101)
    for c in pop:
        simulate_assessment(c, rng, params)
        c._fsp = mv._fsp_profile(c, rng)
    profiles = [mv.to_profile(c, rng) for c in pop]
    needs = mv.make_needs(60, rng)
    by = {c.idx: c for c in pop}
    for name in ("filters", "ours"):
        cnt = Counter()
        labels_cnt = Counter()
        for nd in needs:
            ranked = mv.rank_filters(nd, pop) if name == "filters" else mv.rank_ours(mv.need_obj(nd), profiles)
            for i in ranked[:10]:
                c = by[i]
                lab = mv.relevance(c, nd)
                labels_cnt[lab] += 1
                if lab < 2:
                    for r in reasons(c, nd) or ["other"]:
                        cnt[r] += 1
        print(name, "labels in top10:", dict(sorted(labels_cnt.items())), "| failure reasons:", dict(cnt.most_common()))


if __name__ == "__main__":
    main()
