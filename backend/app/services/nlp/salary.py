"""Единое соглашение по зарплатам: все суммы на платформе — в месяц до вычета НДФЛ (gross).

Постановщики просили явно подписывать, gross это или net. Если в тексте вакансии или резюме сумма указана «на руки»,
она пересчитывается в gross по прогрессивной шкале НДФЛ (с 2025 г.: 13% до 2,4 млн ₽ в год, 15% до 5 млн, 18% до
20 млн, 20% до 50 млн, 22% свыше), чтобы ожидания кандидата и вилка работодателя сравнивались на одной базе.
"""
from __future__ import annotations

import re

NDFL_SCALE = [(2_400_000, 0.13), (5_000_000, 0.15), (20_000_000, 0.18), (50_000_000, 0.20), (float("inf"), 0.22)]
NET_RE = re.compile(r"на\s+рук[иу]|чистыми|после\s+(?:вычета|налог)|\bnet\b|нетто", re.I)
GROSS_RE = re.compile(r"до\s+(?:вычета|налог|ндфл)|\bgross\b|брутто|с\s+учётом\s+ндфл", re.I)


def ndfl_year(gross_year: float) -> float:
    tax, prev = 0.0, 0.0
    for limit, rate in NDFL_SCALE:
        if gross_year <= prev:
            break
        tax += (min(gross_year, limit) - prev) * rate
        prev = limit
    return tax


def net_to_gross_monthly(net: int) -> int:
    """Месячная сумма «на руки» → до вычета НДФЛ (бинарный поиск по прогрессивной шкале), до 1000 ₽."""
    lo, hi = float(net), float(net) * 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if mid - ndfl_year(mid * 12) / 12 < net:
            lo = mid
        else:
            hi = mid
    return int(round(hi / 1000) * 1000)


def is_net(text: str) -> bool:
    """Сумма указана «на руки» (а не до вычета НДФЛ)."""
    return bool(NET_RE.search(text)) and not GROSS_RE.search(text)
