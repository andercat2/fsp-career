"""Общие метрики и утилиты процедуры валидации."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from app.services.matching.metrics import mrr, ndcg_at_k, precision_at_k  # noqa: F401 — общие с POST /eval/dataset

REPORTS = Path(__file__).resolve().parent / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def save_report(name: str, data: dict) -> Path:
    path = REPORTS / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_default), encoding="utf-8", newline="\n")
    return path


def _default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    raise TypeError(type(o))


def r3(x: float) -> float:
    return round(float(x), 3)


def cohen_kappa(a: list, b: list) -> float:
    n = len(a)
    labels = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[label] * cb[label] for label in labels) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def weighted_kappa(a: list[int], b: list[int], k: int) -> float:
    """Квадратично взвешенная каппа для порядковых классов (грейды)."""
    o = np.zeros((k, k))
    for x, y in zip(a, b, strict=True):
        o[x, y] += 1
    w = np.array([[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)])
    e = np.outer(o.sum(1), o.sum(0)) / o.sum()
    return float(1 - (w * o).sum() / (w * e).sum())


def point_biserial(u: list[int], x: list[float]) -> float:
    u_arr, x_arr = np.array(u, dtype=float), np.array(x, dtype=float)
    if u_arr.std() == 0 or x_arr.std() == 0:
        return 0.0
    return float(np.corrcoef(u_arr, x_arr)[0, 1])


def gini(values: list[float]) -> float:
    v = np.sort(np.array(values, dtype=float))
    if v.sum() == 0:
        return 0.0
    n = len(v)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum()))
