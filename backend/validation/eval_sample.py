"""Пример набора для стенда проверки подбора (страница /evaluate, POST /eval/dataset).

Синтетическая популяция с симулированным тестом и потребности работодателей — как в собственной валидации подбора
(matching_validation.py), с истинной релевантностью пар 0–3 по скрытым данным. У каждого кандидата — текст резюме
(в нём заявленный, а не истинный грейд), у прошедших тест — ещё и категория по тесту. На странице можно сравнить
выдачу с категориями по тесту, только по тексту резюме и поиск по ключевым словам.

    cd backend && python -m validation.eval_sample      →  frontend/public/eval-sample.json
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from app.seed.synthetic import default_params, generate_population, simulate_assessment
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import GRADE_NAMES
from validation.matching_validation import make_needs, relevance

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "eval-sample.json"
FORMATS = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}


def resume_text(c) -> str:
    skills = ", ".join(SKILL_BY_ID[s].name for s in c.declared_skills if s in SKILL_BY_ID)
    jobs = "\n".join(f"{e['position']}, {e['company']}: {e['description']}" for e in c.experience[:3])
    return (f"{c.headline}. Уровень: {GRADE_NAMES[c.claimed_grade]}. Опыт работы {c.experience_years:.1f} лет.\n"
            f"Навыки: {skills}.\n{jobs}\n{c.about}\n"
            f"Город: {c.city}{', готов к переезду' if c.relocation else ''}. Формат: "
            f"{', '.join(FORMATS[f] for f in c.work_formats)}. Ожидания: {c.desired_salary:,} руб.".replace(",", " "))


def main(n_candidates: int = 240, n_needs: int = 8, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    random.seed(seed)
    params = default_params()
    pop = generate_population(n_candidates, seed=seed)
    for c in pop:
        simulate_assessment(c, rng, params)
    needs = make_needs(n_needs, rng)
    cid = {c.idx: f"c{c.idx + 1:03d}" for c in pop}
    data = {
        "about": "Синтетический набор: 240 кандидатов (у прошедших тест — категория, у всех — текст резюме с заявленным "
                 "грейдом), 8 потребностей и истинная релевантность пар 0–3 по скрытым данным популяции.",
        "vacancies": [{"id": f"v{nd['id'] + 1}", "title": nd["title"], "text": nd["text"]} for nd in needs],
        "candidates": [{"id": cid[c.idx], "text": resume_text(c),
                        **({"specialization": c.spec, "grade": c.grade, "theta": round(c.theta_hat, 2)} if c.grade else {})}
                       for c in pop],
        "labels": [{"vacancy": f"v{nd['id'] + 1}", "candidate": cid[c.idx], "relevance": r}
                   for nd in needs for c in pop if (r := relevance(c, nd)) > 0],
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: вакансий {len(data['vacancies'])}, кандидатов {len(data['candidates'])} "
          f"(с категорией {sum('grade' in c for c in data['candidates'])}), меток {len(data['labels'])}, "
          f"{OUT.stat().st_size // 1024} КБ")
    return data


if __name__ == "__main__":
    main()
