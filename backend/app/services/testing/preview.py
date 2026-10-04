"""Как система формирует задания и тесты по описанию вакансии (демонстрация механики для работодателя).

1. Из вакансии берётся специализация и язык → базовый блюпринт специализации (доли доменов).
2. Обязательные навыки вакансии усиливают свои тестовые домены (+0.06), желательные (+0.03).
3. Для каждого домена подбираются семейства заданий, наиболее информативные на уровне грейда вакансии.
4. Каждое семейство рендерится в уникальный вариант — показываем несколько вариантов одного семейства,
   чтобы было видно: структура и трудность одинаковые, конкретные данные и ответы — разные.
"""
from __future__ import annotations

import random

from app.models import Vacancy
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import DOMAINS, GRADE_NAMES, grade_center, resolve_blueprint
from app.services.testing import irt
from app.services.testing.bank import BY_DOMAIN


def vacancy_blueprint(v: Vacancy) -> tuple[dict[str, float], list[dict]]:
    bp = dict(resolve_blueprint(v.specialization, v.language))
    boosts = []
    for skills, w, kind in ((v.must_skills or [], 0.06, "обязательный"), (v.nice_skills or [], 0.03, "желательный")):
        for sid in skills:
            sk = SKILL_BY_ID.get(sid)
            if not sk:
                continue
            for d in sk.domains:
                if d in BY_DOMAIN:
                    bp[d] = bp.get(d, 0.0) + w
                    boosts.append({"skill": sk.name, "domain": DOMAINS.get(d, d), "kind": kind, "delta": w})
    total = sum(bp.values())
    return {k: round(v / total, 4) for k, v in sorted(bp.items(), key=lambda kv: -kv[1])}, boosts


def _public(r) -> dict:
    return {"prompt": r.prompt, "kind": r.kind, "options": r.options, "code": r.code, "code_lang": r.code_lang,
            "answer": r.key, "explanation": r.explanation}


def vacancy_test_preview(v: Vacancy, n_items: int = 8, seed: int | None = None) -> dict:
    rng = random.Random(seed if seed is not None else v.id * 7919)
    bp, boosts = vacancy_blueprint(v)
    grade = (v.grades or ["middle"])[0]
    theta = grade_center(grade)
    domains = list(bp)[:n_items]
    items = []
    for dom in domains:
        fams = sorted(BY_DOMAIN[dom], key=lambda f: -float(irt.information(theta, f.a, f.b, f.c)))[:4]
        fam = rng.choice(fams)
        r = fam.render(rng.getrandbits(48), v.language)
        items.append({"family_id": fam.id, "domain": dom, "domain_name": DOMAINS.get(dom, dom), "topic": fam.topic,
                      "level": fam.level, "parametric": fam.parametric, "difficulty_b": fam.b, **_public(r)})
    param = next((f for d in domains for f in BY_DOMAIN[d] if f.parametric), None)
    variants = []
    if param:
        for _ in range(3):
            r = param.render(rng.getrandbits(48), v.language)
            variants.append(_public(r))
    return {
        "vacancy_id": v.id, "grade": grade, "grade_name": GRADE_NAMES[grade], "theta_target": theta,
        "blueprint": [{"domain": d, "name": DOMAINS.get(d, d), "weight": w} for d, w in bp.items()],
        "boosts": boosts, "items": items,
        "uniqueness_demo": {"family_id": param.id if param else None, "topic": param.topic if param else None,
                            "variants": variants},
        "how_it_works": [
            "Блюпринт специализации задаёт доли тестовых доменов; навыки из вакансии усиливают соответствующие домены.",
            "Адаптивный алгоритм выбирает следующее задание по максимуму информации при текущей оценке уровня.",
            "Каждое задание — вариант семейства с откалиброванной трудностью: у кандидатов разные данные и ответы, "
            "но одинаковая сложность, поэтому результаты сопоставимы.",
        ],
    }
