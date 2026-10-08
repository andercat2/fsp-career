"""Детектор «чужого варианта»: ответ, совпадающий с правильным ответом ДРУГОГО варианта того же семейства.

Параметрические задания у каждого кандидата свои, поэтому списанный ответ не подходит. Более того, его попытка —
сильная улика: для семейств с разнообразными ответами случайное совпадение с ключом чужого варианта маловероятно.
Индекс «пригодных» семейств строится один раз (в фоне при старте): оценивается вероятность коллизии ключей двух
случайных вариантов; детектор применяется только там, где она < 2%.
"""
from __future__ import annotations

import threading
from collections import Counter

from app.services.testing.bank import REGISTRY
from app.services.testing.bank.core import _norm_tokens

COLLISION_MAX = 0.02
SAMPLES = 60
_index: dict[str, float] | None = None
_lock = threading.Lock()


def norm_answer(kind: str, value) -> str | None:
    if value is None:
        return None
    if kind == "numeric":
        try:
            return f"{float(str(value).replace(',', '.').replace(' ', '')):.4f}"
        except ValueError:
            return None
    return _norm_tokens(str(value))


def build_index() -> dict[str, float]:
    global _index
    with _lock:
        if _index is not None:
            return _index
        out = {}
        for fam in list(REGISTRY.values()):
            if not fam.parametric or fam.kind not in ("input", "numeric"):
                continue
            keys = [norm_answer(fam.kind, fam.render(10_000 + s).key) for s in range(SAMPLES)]
            cnt = Counter(keys)
            n = len(keys)
            coll = sum(v * (v - 1) for v in cnt.values()) / (n * (n - 1))
            if coll < COLLISION_MAX:
                out[fam.id] = round(coll, 4)
        _index = out
        return out


def detectable(family_id: str) -> float | None:
    """Вероятность случайной коллизии для пригодного семейства; None — детектор неприменим (или индекс не готов)."""
    if _index is None:
        return None
    return _index.get(family_id)
