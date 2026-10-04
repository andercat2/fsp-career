"""Модель IRT (3PL) и байесовская оценка способности кандидата.

P(верно | θ) = c + (1 - c) / (1 + exp(-a(θ - b)))
  a — дискриминативность (насколько резко задание разделяет слабых и сильных),
  b — трудность (θ, при котором вероятность верного ответа посередине между c и 1),
  c — вероятность угадать (для выбора из 4 вариантов ≈ 0.2, для ввода ответа ≈ 0).

Оценка θ — EAP (апостериорное среднее) на сетке. Prior одинаковый для всех кандидатов, поэтому результаты
разных кандидатов, получивших разные задания, лежат на одной шкале и сопоставимы.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

GRID = np.linspace(-4.0, 4.0, 161)
PRIOR_MEAN = 0.0
PRIOR_SD = 1.25
_LOG_PRIOR = -0.5 * ((GRID - PRIOR_MEAN) / PRIOR_SD) ** 2


def prob(theta: float | np.ndarray, a: float, b: float, c: float) -> float | np.ndarray:
    return c + (1.0 - c) / (1.0 + np.exp(-a * (theta - b)))


def information(theta: float | np.ndarray, a: float, b: float, c: float) -> float | np.ndarray:
    """Информация Фишера 3PL: I(θ) = a² · (P − c)² / (1 − c)² · (1 − P) / P."""
    p = prob(theta, a, b, c)
    return (a**2) * ((p - c) ** 2 / (1.0 - c) ** 2) * ((1.0 - p) / p)


def log_likelihood_grid(responses: Sequence[tuple[float, float, float, bool]]) -> np.ndarray:
    ll = np.zeros_like(GRID)
    for a, b, c, u in responses:
        p = np.clip(prob(GRID, a, b, c), 1e-9, 1 - 1e-9)
        ll += np.log(p) if u else np.log(1.0 - p)
    return ll


def eap(responses: Sequence[tuple[float, float, float, bool]]) -> tuple[float, float]:
    """Возвращает (θ̂, SE) — апостериорные среднее и стандартное отклонение."""
    log_post = _LOG_PRIOR + log_likelihood_grid(responses)
    log_post -= log_post.max()
    w = np.exp(log_post)
    w /= w.sum()
    mean = float((GRID * w).sum())
    sd = float(math.sqrt(max(((GRID - mean) ** 2 * w).sum(), 1e-12)))
    return mean, sd


def posterior_prob_above(responses: Sequence[tuple[float, float, float, bool]], cut: float) -> float:
    """P(θ ≥ cut | ответы) — используется в правиле досрочной остановки и при классификации грейда."""
    log_post = _LOG_PRIOR + log_likelihood_grid(responses)
    log_post -= log_post.max()
    w = np.exp(log_post)
    w /= w.sum()
    return float(w[GRID >= cut].sum())


def person_fit_lz(theta: float, responses: Sequence[tuple[float, float, float, bool]]) -> float | None:
    """Стандартизованная статистика согласия lz (Drasgow et al., 1985).

    Сильно отрицательные значения (lz < −2) — «невозможный» паттерн: например, решены трудные задания и
    провалены лёгкие. Типичный след заранее известных ответов, поэтому сессия помечается для проверки.
    """
    if len(responses) < 6:
        return None
    l0 = e = v = 0.0
    for a, b, c, u in responses:
        p = float(np.clip(prob(theta, a, b, c), 1e-6, 1 - 1e-6))
        l0 += math.log(p) if u else math.log(1 - p)
        e += p * math.log(p) + (1 - p) * math.log(1 - p)
        v += p * (1 - p) * math.log(p / (1 - p)) ** 2
    if v <= 1e-9:
        return None
    return (l0 - e) / math.sqrt(v)


def test_information(theta: np.ndarray, items: Sequence[tuple[float, float, float]]) -> np.ndarray:
    total = np.zeros_like(theta, dtype=float)
    for a, b, c in items:
        total += information(theta, a, b, c)
    return total


B_GRID = np.linspace(-3.0, 3.0, 121)


def calibrate_b(u: Sequence[int | bool], thetas: Sequence[float], a: float, c: float) -> float:
    """Онлайн-калибровка трудности задания при фиксированных θ̂ кандидатов (MLE на сетке, векторно)."""
    th = np.asarray(thetas, dtype=float)[:, None]
    uu = np.asarray(u, dtype=float)[:, None]
    p = np.clip(c + (1.0 - c) / (1.0 + np.exp(-a * (th - B_GRID[None, :]))), 1e-6, 1 - 1e-6)
    ll = (uu * np.log(p) + (1 - uu) * np.log(1 - p)).sum(axis=0)
    return float(B_GRID[int(np.argmax(ll))])
