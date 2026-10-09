"""Стенд проверки подбора на чужом наборе пар «вакансия — кандидат» с разметкой релевантности (POST /eval/dataset).

Жюри или работодатель загружает вакансии, кандидатов и метки релевантности — система строит выдачу по каждой
вакансии тем же ранжированием, что и в продукте, и считает P@k, nDCG@k и MRR рядом с поиском по ключевым словам
(TF-IDF) на тех же данных. Ничего не сохраняется.

Кандидат задаётся двумя способами:
- с категорией по тесту (specialization + grade, при желании θ и подтверждённые навыки) — как в продукте;
- только текстом резюме — NLP определяет специализацию, навыки, заявленный грейд, ожидания и формат работы, а
  категория получает статус «не подтверждён»: так продукт показывает кандидатов, чей грейд тест пока не подтвердил.
"""
from __future__ import annotations

import re

from app.models import CandidateProfile
from app.services.fsp.scoring import fsp_score
from app.services.matching.metrics import mrr, ndcg_at_k, precision_at_k
from app.services.matching.profile import W_FSP, W_TEST, test_position
from app.services.matching.ranking import RELATED_SPECS, Need, in_categories, score_candidates
from app.services.nlp.resume_parser import claimed_grade_from, parse_resume_text
from app.services.nlp.vacancy_parser import parse_need
from app.services.reference.skills import SKILL_BY_ID, extract_skills
from app.services.reference.taxonomy import GRADE_CODES, GRADE_INDEX, GRADE_NAMES, SPEC_NAMES, grade_center

_YEARS = re.compile(r"(?:опыт|стаж)\w*[^.\n]{0,40}?(\d{1,2}(?:[.,]\d)?)\s*(?:\+\s*)?(?:лет|года|год)", re.I)


def _skill_ids(names: list[str]) -> list[str]:
    """Навыки по коду онтологии («python») или по названию («PostgreSQL», «Docker»)."""
    ids = [n for n in names if n in SKILL_BY_ID]
    rest = [n for n in names if n not in SKILL_BY_ID]
    if rest:
        ids += [s["id"] for s in extract_skills(", ".join(rest))]
    return list(dict.fromkeys(ids))


def candidate_profile(c, idx: int) -> tuple[CandidateProfile, str]:
    """Профиль для ранжирования и описание категории. c — EvalDatasetCandidate (или совместимая схема)."""
    text = (c.text or "").strip()
    parsed = parse_resume_text(text) if text else {}
    skills = _skill_ids(c.skills) if c.skills else parsed.get("skills") or []
    common = dict(id=idx, public_id=c.id, skills=skills, verified_skills=_skill_ids(c.verified_skills),
                  desired_salary=c.desired_salary or parsed.get("desired_salary"),
                  work_formats=c.work_formats or parsed.get("work_formats") or [], city=c.city or parsed.get("city"),
                  relocation=bool(parsed.get("relocation")), headline=parsed.get("headline"), about=text,
                  domain_scores={}, open_to_offers=True, tasks_done=0, privacy={},
                  fsp_profile={"achievements": c.fsp_achievements} if c.fsp_achievements else None)
    if c.specialization and c.grade:  # категория по тесту
        p = CandidateProfile(**common, grade=c.grade, grade_specialization=c.specialization, specialization=c.specialization,
                             grade_theta=c.theta if c.theta is not None else grade_center(c.grade))
        label = f"{SPEC_NAMES.get(c.specialization, c.specialization)} · {GRADE_NAMES[c.grade]}"
    else:  # только резюме: грейд заявленный, статус «не подтверждён»
        spec = c.specialization or parsed.get("specialization") or "backend"
        m = _YEARS.search(text)
        years = parsed.get("experience_years") or (float(m.group(1).replace(",", ".")) if m else None)
        grade = parsed.get("claimed_grade") or claimed_grade_from(text, years) or "middle"
        p = CandidateProfile(**common, grade=None, specialization=spec, claimed_grade=grade, unconfirmed_grade=grade,
                             unconfirmed_theta=c.theta if c.theta is not None else grade_center(grade))
        label = f"{SPEC_NAMES.get(spec, spec)} · {GRADE_NAMES[grade]} (из резюме, не подтверждён)"
    p.fsp_score = fsp_score(p.fsp_profile, p.grade_specialization)
    p.strength = round(W_TEST * test_position(p) + W_FSP * p.fsp_score, 4) if p.grade else 0.0
    return p, label


def rank_need(need: Need, profiles: list[CandidateProfile]) -> list[dict]:
    """Выдача как в продукте: пул — рекомендованные категории (грейды потребности и соседние, смежные
    специализации), затем ранжирование с объяснением. Кандидаты вне этих категорий в выдачу не попадают."""
    pairs = {(need.specialization, g) for g in need.grades}
    lo, hi = min(GRADE_INDEX[g] for g in need.grades), max(GRADE_INDEX[g] for g in need.grades)
    if lo > 0:
        pairs.add((need.specialization, GRADE_CODES[lo - 1]))
    if hi < len(GRADE_CODES) - 1:
        pairs.add((need.specialization, GRADE_CODES[hi + 1]))
    for rel in RELATED_SPECS.get(need.specialization, {}):
        pairs |= {(rel, g) for g in need.grades}
    return score_candidates(need, [p for p in profiles if in_categories(p, pairs)])


def rank_keyword(vacancy_texts: list[str], candidate_docs: list[str]) -> list[list[int]]:
    """Базовая линия «поиск по ключевым словам»: TF-IDF-близость текста вакансии и резюме."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    m = TfidfVectorizer(sublinear_tf=True).fit_transform(vacancy_texts + candidate_docs)
    sims = linear_kernel(m[:len(vacancy_texts)], m[len(vacancy_texts):])
    return [list((-row).argsort()) for row in sims]


def _metrics(order: list[str], labels: dict[str, int], k: int, thr: int) -> dict:
    rels = [labels.get(cid, 0) for cid in order]
    return {"p_at_k": round(precision_at_k(rels, k, thr), 3), "ndcg": round(ndcg_at_k(rels, k, list(labels.values())), 3),
            "mrr": round(mrr(rels, thr), 3), "relevant_in_top": sum(r >= thr for r in rels[:k])}


def evaluate_dataset(data) -> dict:
    """data — EvalDatasetIn: vacancies, candidates, labels (метки 0–3 или 0/1), k."""
    k = data.k
    labels: dict[str, dict[str, int]] = {}
    for lb in data.labels:
        labels.setdefault(lb.vacancy, {})[lb.candidate] = lb.relevance
    top_label = max((lb.relevance for lb in data.labels), default=1)
    thr = 1 if top_label <= 1 else 2  # бинарная разметка — релевантен при 1, шкала 0–3 — при ≥ 2

    profiles, categories = [], {}
    for i, c in enumerate(data.candidates, 1):
        p, label = candidate_profile(c, i)
        profiles.append(p)
        categories[c.id] = label
    docs = [f"{c.text} {' '.join(SKILL_BY_ID[s].name for s in p.skills if s in SKILL_BY_ID)}"
            for c, p in zip(data.candidates, profiles, strict=True)]
    keyword = rank_keyword([f"{v.title}\n{v.text}" for v in data.vacancies], docs)
    ids = [c.id for c in data.candidates]

    rows = []
    for v, kw_order in zip(data.vacancies, keyword, strict=True):
        parsed = parse_need(v.text, v.title)
        need = Need.from_dict(parsed | {"text": v.text, "title": v.title})
        ranked = rank_need(need, profiles)
        ours_order = [r["public_id"] for r in ranked]
        kw_ids = [ids[i] for i in kw_order]
        lv = labels.get(v.id, {})
        rows.append({
            "id": v.id, "title": v.title or parsed.get("title") or v.id,
            "need": {"specialization": SPEC_NAMES.get(need.specialization, need.specialization),
                     "grades": [GRADE_NAMES[g] for g in need.grades],
                     "must_skills": [SKILL_BY_ID[s].name for s in need.must_skills if s in SKILL_BY_ID]},
            "relevant_total": sum(r >= thr for r in lv.values()), "returned": len(ours_order),
            "ours": {**_metrics(ours_order, lv, k, thr),
                     "top": [{"id": r["public_id"], "score": r["score"], "label": lv.get(r["public_id"], 0),
                              "category": categories[r["public_id"]],
                              "reasons": [x["text"] for x in r["reasons"] if x["kind"] == "plus"][:2]} for r in ranked[:k]]},
            "keyword": {**_metrics(kw_ids, lv, k, thr),
                        "top": [{"id": cid, "label": lv.get(cid, 0), "category": categories[cid]} for cid in kw_ids[:k]]},
        })
    scored = [r for r in rows if r["relevant_total"]]  # вакансии без релевантных меток в среднее не входят

    def avg(system: str, key: str) -> float | None:
        return round(sum(r[system][key] for r in scored) / len(scored), 3) if scored else None

    return {
        "k": k, "threshold": thr, "vacancies_scored": len(scored),
        "candidates": {"total": len(profiles), "with_category": sum(1 for p in profiles if p.grade),
                       "text_only": sum(1 for p in profiles if not p.grade)},
        "summary": {s: {m: avg(s, m) for m in ("p_at_k", "ndcg", "mrr")} for s in ("ours", "keyword")},
        "vacancies": rows,
    }
