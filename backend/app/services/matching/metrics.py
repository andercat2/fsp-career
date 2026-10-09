"""Метрики качества выдачи: доля релевантных в топе (P@k), nDCG@k, MRR. Ими пользуются и собственная валидация
(validation/matching_validation.py), и стенд проверки на наборе пар «вакансия — кандидат» (POST /eval/dataset).

rels — метки релевантности в порядке выдачи: 0–3 (релевантным считается ≥ thr) или бинарные 0/1 (thr = 1)."""
import math


def ndcg_at_k(rels: list[int], k: int, ideal: list[int]) -> float:
    def dcg(rs):
        return sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rs[:k]))

    idcg = dcg(sorted(ideal, reverse=True))
    return dcg(rels) / idcg if idcg > 0 else 0.0


def precision_at_k(rels: list[int], k: int, thr: int = 2) -> float:
    top = rels[:k]
    return sum(r >= thr for r in top) / k if top else 0.0


def mrr(rels: list[int], thr: int = 2) -> float:
    for i, r in enumerate(rels):
        if r >= thr:
            return 1 / (i + 1)
    return 0.0
