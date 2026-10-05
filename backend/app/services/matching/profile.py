"""Сила подтверждённого профиля кандидата — основа ранжирования внутри категории.

strength = 0.60 · test + 0.25 · fsp + 0.15 · activity
  test     — положение θ внутри полосы присвоенного грейда (выше в полосе — сильнее), только по тесту;
  fsp      — агрегированный сигнал достижений ФСП, релевантных специализации (0, если истории нет);
  activity — регулярные задания работодателей с затуханием по давности (свежесть профиля).
Самоописание резюме в силу профиля не входит: оно влияет только на объяснения и текстовую близость.
"""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import CandidateProfile
from app.services.fsp.scoring import fsp_score
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import grade_band

W_TEST, W_FSP, W_ACTIVITY = 0.60, 0.25, 0.15
VERIFY_THRESHOLD = 0.5
TASK_HALF_LIFE_DAYS = 60

# Навыки, которые домен теста измеряет НАПРЯМУЮ. Только они могут получить статус «подтверждён тестом»
# (или «не подтвердился»). Знание конкретных инструментов (Kafka, Spring, PyTorch) общий домен не проверяет —
# такие навыки остаются заявленными.
VERIFIABLE = {
    "python": ["python"], "java": ["java"], "go": ["go"], "javascript": ["javascript"], "typescript": ["typescript"],
    "react": ["react"], "web_layout": ["html", "css", "a11y"], "browser": ["browser_apis", "web_perf"],
    "sql": ["sql", "postgresql", "mysql", "mssql", "oracle", "clickhouse"], "databases": ["db_design"],
    "http_api": ["rest"], "security": ["security_web"], "linux": ["linux", "bash"], "networks": ["networks"],
    "containers": ["docker"], "kubernetes": ["kubernetes"], "cicd": ["git", "gitlab_ci"],
    "observability": ["prometheus", "sre"], "statistics": ["statistics"], "analytics": ["product_metrics", "ab_testing"],
    "data_tools": ["pandas", "numpy"], "ml": ["scikit_learn", "gradient_boosting", "machine_learning"],
    "deep_learning": ["deep_learning", "pytorch", "tensorflow"], "algorithms": ["algorithms"],
    "testing_theory": ["test_design", "manual_testing"], "test_automation": ["pytest", "selenium"],
}
SKILL_VERIFIER = {sk: d for d, sks in VERIFIABLE.items() for sk in sks}
# Навыки, совпадающие с доменом по смыслу: подтверждаются даже без упоминания в резюме
DOMAIN_CORE_SKILLS = {
    "sql": ["sql"], "python": ["python"], "java": ["java"], "go": ["go"], "javascript": ["javascript"],
    "typescript": ["typescript"], "react": ["react"], "web_layout": ["html", "css"], "algorithms": ["algorithms"],
    "linux": ["linux"], "containers": ["docker"], "kubernetes": ["kubernetes"], "statistics": ["statistics"],
    "testing_theory": ["test_design"], "http_api": ["rest"], "data_tools": ["pandas"], "ml": ["scikit_learn"],
    "analytics": ["product_metrics"], "databases": ["db_design"], "networks": ["networks"], "browser": ["browser_apis"],
}


THETA_FLOOR, THETA_CEIL = -2.0, 2.5  # практические границы открытых полос «Стажёр» и «Senior»


def _band_position(theta: float, lo: float, hi: float) -> float:
    lo = THETA_FLOOR if math.isinf(lo) else lo
    hi = THETA_CEIL if math.isinf(hi) else hi
    return max(0.0, min(1.0, 0.15 + 0.85 * (theta - lo) / (hi - lo)))


def test_position(cand: CandidateProfile) -> float:
    """Положение θ внутри полосы присвоенного грейда — тестовая часть хранимой силы профиля."""
    if not cand.grade or cand.grade_theta is None:
        return 0.0
    return _band_position(cand.grade_theta, *grade_band(cand.grade))


def strength_for(cand: CandidateProfile, grades: list[str]) -> float:
    """Сила профиля относительно потребности: тестовая часть считается по полосе ЗАПРОШЕННЫХ грейдов.

    Хранимая сила меряет θ внутри собственного грейда кандидата, поэтому Junior у верхней границы своей полосы
    выглядел бы «сильнее» Middle у нижней. Для подборки на Middle важен уровень на общей шкале θ относительно
    требований; внутри одной категории порядок кандидатов при этом не меняется (монотонное преобразование θ)."""
    if not cand.grade or cand.grade_theta is None or not grades:
        return cand.strength or 0.0
    lo = min(grade_band(g)[0] for g in grades)
    hi = max(grade_band(g)[1] for g in grades)
    shift = W_TEST * (_band_position(cand.grade_theta, lo, hi) - test_position(cand))
    return max(0.0, min(1.0, (cand.strength or 0.0) + shift))


def activity_score(cand: CandidateProfile) -> float:
    if not cand.tasks_done or not cand.last_task_at:
        return 0.0
    days = max(0.0, (utcnow() - cand.last_task_at).days)
    decay = 0.5 ** (days / TASK_HALF_LIFE_DAYS)
    volume = 1 - math.exp(-cand.tasks_done / 3)
    quality = cand.tasks_score or 0.5
    return round(volume * decay * (0.4 + 0.6 * quality), 4)


def verifier_domain(skill_id: str) -> str | None:
    """Домен теста, который напрямую измеряет навык (None — тест навык не проверяет)."""
    return SKILL_VERIFIER.get(skill_id)


def verified_skills(cand: CandidateProfile) -> list[str]:
    """Заявленные навыки, чей проверяющий домен пройден на уровне ≥ порога, + навыки пройденных доменов
    «по смыслу» (SQL для домена SQL и т. п.)."""
    scores = cand.domain_scores or {}
    passed = {d for d, v in scores.items() if v.get("score", 0) >= VERIFY_THRESHOLD and v.get("n", 0) >= 1}
    out: list[str] = []
    for sid in cand.skills or []:
        if verifier_domain(sid) in passed:
            out.append(sid)
    for d in passed:
        for sid in DOMAIN_CORE_SKILLS.get(d, []):
            if sid not in out:
                out.append(sid)
    return out


def profile_completeness(cand: CandidateProfile) -> float:
    fields = [cand.full_name, cand.city, cand.headline, cand.about, cand.experience_years is not None,
              bool(cand.skills), bool(cand.experience), cand.desired_salary, bool(cand.work_formats)]
    return sum(bool(f) for f in fields) / len(fields)


def recompute_candidate(db: Session, cand: CandidateProfile) -> None:
    cand.fsp_score = fsp_score(cand.fsp_profile, cand.grade_specialization or cand.specialization)
    cand.verified_skills = verified_skills(cand)
    test = test_position(cand)
    cand.strength = round(W_TEST * test + W_FSP * cand.fsp_score + W_ACTIVITY * activity_score(cand), 4) if cand.grade else 0.0
    db.flush()


def strength_breakdown(cand: CandidateProfile) -> dict:
    return {
        "test": round(test_position(cand), 3),
        "fsp": round(cand.fsp_score or 0.0, 3),
        "activity": round(activity_score(cand), 3),
        "completeness": round(profile_completeness(cand), 3),
        "weights": {"test": W_TEST, "fsp": W_FSP, "activity": W_ACTIVITY},
        "total": round(cand.strength or 0.0, 3),
    }
