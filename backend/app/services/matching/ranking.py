"""Механика подбора: потребность работодателя → рекомендованные категории → ранжированные кандидаты с объяснением.

Пул кандидатов формируется только из категорий, присвоенных тестированием (специализация × грейд), а не из
самоописания. Внутри пула релевантность:

  score = (0.30·skills + 0.25·strength + 0.20·category + 0.15·conditions + 0.10·text) · availability

  skills       — покрытие обязательных навыков с учётом свидетельств теста на уровне требуемого грейда (см.
                 skill_value): подтверждён тестом 0.8, заявлен 0.65, не подтвердился 0.4, смежный навык 0.3;
                 плюс бонус за «желательные» навыки. Проверяются только навыки, которые домен теста измеряет
                 напрямую (profile.VERIFIABLE);
  strength     — сила подтверждённого профиля (тест + ФСП + активность), см. profile.py; тестовая часть
                 считается относительно полосы запрошенных грейдов (profile.strength_for);
  category     — специализация (смежные — с коэффициентом) × соответствие грейду: половина — совпадение
                 присвоенного грейда, половина — апостериорная вероятность, что уровень θ лежит в запрошенных
                 грейдах (учитывает погрешность теста у границ);
  conditions   — ожидания по доходу vs вилка, формат, город;
  text         — TF-IDF-близость описания потребности и текстов профиля;
  availability — мультипликативный штраф за фактическую недоступность (другой город без релокации, ожидания
                 заметно выше вилки, несовместимый формат) — такие кандидаты остаются видимыми, но ниже.
Параметры подобраны и проверены на синтетическом наборе пар (validation/matching_validation.py).

Каждая компонента порождает человекочитаемые причины (+/−), которые показываются работодателю.

Единица пула — резюме: у кандидата может быть несколько резюме под разные специализации, каждое со своей
категорией по тесту (services/resumes.py). В выдаче кандидат показывается один раз — с лучшим для потребности резюме.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import CandidateProfile, CandidateResume, User
from app.services.fsp.scoring import fsp_summary
from app.services.matching.profile import strength_for, verifier_domain
from app.services.reference.skills import SKILL_BY_ID
from app.services.resumes import ResumeView
from app.services.reference.taxonomy import (
    DOMAINS,
    GRADE_CODES,
    GRADE_INDEX,
    GRADE_NAMES,
    SPEC_BY_CODE,
    SPEC_NAMES,
    WORK_FORMATS,
    grade_band,
    grade_center,
)

WEIGHTS = {"skills": 0.30, "strength": 0.25, "category": 0.20, "conditions": 0.15, "text": 0.10}
RELATED_SPECS = {
    "backend": {"fullstack": 0.6},
    "frontend": {"fullstack": 0.6},
    "fullstack": {"backend": 0.55, "frontend": 0.55},
    "ml": {"data_analyst": 0.4},
    "data_analyst": {"ml": 0.5},
    "devops": {"backend": 0.3},
    "qa": {},
}


@dataclass
class Need:
    specialization: str
    grades: list[str]
    must_skills: list[str]
    nice_skills: list[str]
    salary_from: int | None = None
    salary_to: int | None = None
    work_format: str | None = None
    city: str | None = None
    text: str = ""
    title: str = ""
    require_fsp: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> Need:
        return cls(
            specialization=d["specialization"], grades=list(d.get("grades") or ["middle"]),
            must_skills=list(d.get("must_skills") or []), nice_skills=list(d.get("nice_skills") or []),
            salary_from=d.get("salary_from"), salary_to=d.get("salary_to"), work_format=d.get("work_format"),
            city=d.get("city"), text=d.get("text") or d.get("description") or "", title=d.get("title") or "",
            require_fsp=bool(d.get("require_fsp")),
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# ------------------------------------------------------------------ компоненты

def spec_factor(need_spec: str, cand_spec: str | None) -> float:
    if cand_spec == need_spec:
        return 1.0
    return RELATED_SPECS.get(need_spec, {}).get(cand_spec or "", 0.0)


def grade_fit(need_grades: list[str], grade: str | None) -> float:
    if not grade:
        return 0.0
    if grade in need_grades:
        return 1.0
    idx = GRADE_INDEX[grade]
    lo = min(GRADE_INDEX[g] for g in need_grades)
    hi = max(GRADE_INDEX[g] for g in need_grades)
    if idx == lo - 1:
        return 0.45  # растущий кандидат на ступень ниже
    if idx == hi + 1:
        return 0.6  # сильнее, чем нужно: возможен, но дороже
    return 0.1


def _related_skill(sid: str, cand_skills: set[str]) -> str | None:
    sk = SKILL_BY_ID.get(sid)
    if not sk:
        return None
    for other in cand_skills:
        o = SKILL_BY_ID.get(other)
        if o and o.id != sid and o.group == sk.group and set(o.domains) & set(sk.domains):
            return other
    return None


SKILL_VALUES = {"verified": 0.8, "declared": 0.65, "refuted": 0.4, "domain": 0.3, "related": 0.3, "missing": 0.0}


def requirement_level(grades: list[str]) -> float:
    """Минимальный уровень θ, с которого кандидат «тянет» требования: нижняя граница младшего запрошенного грейда
    (для стажёра, у которого полоса открыта снизу, — центр полосы)."""
    lowest = min(grades, key=lambda g: GRADE_INDEX[g])
    lo = grade_band(lowest)[0]
    return grade_center(lowest) if math.isinf(lo) else lo


def skill_value(sid: str, cand: CandidateProfile, level: float = 0.0) -> tuple[float, str, str | None]:
    """(значение, статус, связанный навык) с учётом свидетельств теста на уровне требований потребности.

    Тест здесь отвечает на вопрос «владеет ли кандидат навыком на уровне требований», а не «насколько он силён»:
    уровень уже учтён компонентами категории и силы профиля, повторный учёт θ поднимал бы переквалифицированных.
    Если навык измеряется доменом теста, по доменной оценке θ_d считаем p = σ(1.3·(θ_d − level)), где level —
    нижняя граница требуемого грейда: заявлен и p ≥ 0.5 — «подтверждён» (0.8), p < 0.3 при ≥ 2 заданиях домена —
    «не подтвердился» (0.4), иначе «заявлен» (0.65). Не заявлен, но домен уверенно выше уровня (p ≥ 0.6) — 0.3.
    Не проверялся тестом: заявлен 0.65, смежный навык 0.3, иначе 0. Значения — SKILL_VALUES; вариант с непрерывной
    шкалой владения проигрывал на валидации (validation/matching_validation.py).
    Статусы: verified | declared | refuted | domain | related | missing."""
    declared = set(cand.skills or []) | set(cand.verified_skills or [])
    if cand.primary_language in SKILL_BY_ID:
        declared.add(cand.primary_language)  # основной язык заявлен в опросе и проверен тестом
    scores = cand.domain_scores or {}
    vd = verifier_domain(sid)
    tested = scores.get(vd) if vd else None
    status = None
    if tested and tested.get("n", 0) >= 1:
        th = tested.get("theta")
        prof = 1 / (1 + math.exp(-1.3 * (th - level))) if th is not None else tested.get("score", 0.5)
        if sid in declared:
            status = "verified" if prof >= 0.5 else "refuted" if prof < 0.3 and tested.get("n", 0) >= 2 else "declared"
        elif prof >= 0.6:
            status = "domain"
    elif sid in declared:
        status = "declared"
    if status:
        return SKILL_VALUES[status], status, None
    rel = _related_skill(sid, declared)
    if rel:
        return SKILL_VALUES["related"], "related", rel
    return 0.0, "missing", None


def skills_component(need: Need, cand: CandidateProfile) -> tuple[float, list[dict]]:
    level = requirement_level(need.grades)
    implicit = False
    must = need.must_skills
    if not must:
        must = SPEC_BY_CODE[need.specialization]["core_skills"][:5]
        implicit = True
    details = []
    must_vals = []
    for sid in must:
        v, status, rel = skill_value(sid, cand, level)
        must_vals.append(v)
        details.append({"skill": sid, "name": SKILL_BY_ID[sid].name if sid in SKILL_BY_ID else sid, "status": status,
                        "related": SKILL_BY_ID[rel].name if rel else None, "required": True, "implicit": implicit})
    nice_vals = []
    for sid in need.nice_skills:
        v, status, rel = skill_value(sid, cand, level)
        nice_vals.append(v)
        details.append({"skill": sid, "name": SKILL_BY_ID[sid].name if sid in SKILL_BY_ID else sid, "status": status,
                        "related": SKILL_BY_ID[rel].name if rel else None, "required": False, "implicit": False})
    must_cov = sum(must_vals) / len(must_vals) if must_vals else 0.5
    nice_cov = sum(nice_vals) / len(nice_vals) if nice_vals else 0.0
    return min(1.0, 0.85 * must_cov + 0.15 * nice_cov + (0.15 * must_cov if not nice_vals else 0.0)), details


def salary_fit(need: Need, cand: CandidateProfile) -> tuple[float, str]:
    want = cand.desired_salary
    if not want or not need.salary_to:
        return 0.7, "unknown"
    if want <= need.salary_to:
        return 1.0, "fits"
    if want <= need.salary_to * 1.15:
        return 0.5, "slightly_above"
    return 0.15, "above"


def format_fit(need: Need, cand: CandidateProfile) -> float:
    wf = need.work_format
    formats = cand.work_formats or []
    if not wf or not formats:
        return 0.8
    if wf in formats:
        return 1.0
    return 0.7 if wf == "remote" else 0.3


def city_fit(need: Need, cand: CandidateProfile) -> float:
    if need.work_format == "remote" or not need.city:
        return 1.0
    if cand.city and cand.city.lower() == need.city.lower():
        return 1.0
    return 0.7 if cand.relocation else 0.2


def conditions_component(need: Need, cand: CandidateProfile) -> tuple[float, dict]:
    s, s_status = salary_fit(need, cand)
    f = format_fit(need, cand)
    c = city_fit(need, cand)
    availability = (0.6 if s_status == "above" else 0.9 if s_status == "slightly_above" else 1.0) \
        * (0.5 if c <= 0.2 else 1.0) * (0.75 if f <= 0.3 else 1.0)
    return 0.5 * s + 0.3 * f + 0.2 * c, {"salary": s, "salary_status": s_status, "format": f, "city": c,
                                          "availability": round(availability, 3)}


def band_probability(need_grades: list[str], cand: CandidateProfile) -> float | None:
    """P(θ кандидата лежит в полосах запрошенных грейдов) по нормальной аппроксимации апостериорного θ."""
    if cand.grade_theta is None or not cand.grade_se:
        return None

    def phi(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    total = 0.0
    for g in need_grades:
        lo, hi = grade_band(g)
        p_hi = 1.0 if math.isinf(hi) else phi((hi - cand.grade_theta) / cand.grade_se)
        p_lo = 0.0 if math.isinf(lo) else phi((lo - cand.grade_theta) / cand.grade_se)
        total += max(0.0, p_hi - p_lo)
    return min(1.0, total)


def candidate_text(cand: CandidateProfile) -> str:
    parts = [cand.headline or "", cand.about or ""]
    for e in cand.experience or []:
        parts.append(f"{e.get('position', '')} {e.get('description', '')}")
    parts.append(" ".join(SKILL_BY_ID[s].name for s in (cand.skills or []) if s in SKILL_BY_ID))
    return " ".join(parts)


def text_similarities(need: Need, cands: list[CandidateProfile]) -> list[float]:
    if not cands:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    need_text = " ".join([need.title, need.text, " ".join(SKILL_BY_ID[s].name for s in need.must_skills + need.nice_skills
                                                        if s in SKILL_BY_ID)])
    docs = [need_text] + [candidate_text(c) for c in cands]
    try:
        m = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(docs)
    except ValueError:
        return [0.0] * len(cands)
    sims = linear_kernel(m[0:1], m[1:]).ravel()
    return [float(min(1.0, s / 0.35)) for s in sims]


def response_likelihood(need: Need, cand: CandidateProfile, cond: dict | None = None) -> dict:
    """Оценка вероятности, что кандидат примет приглашение: условия, формат, активность, открытость к предложениям."""
    cond = cond or conditions_component(need, cand)[1]
    days_idle = (utcnow() - (cand.last_active_at or utcnow())).days
    z = -0.4 + 2.2 * (cond["salary"] - 0.5) + 1.0 * (cond["format"] - 0.5) + 0.8 * (cond["city"] - 0.5)
    z += 0.8 if days_idle <= 14 else (-0.6 if days_idle > 60 else 0.0)
    z += 0.6 if cand.open_to_offers else -1.5
    p = 1 / (1 + math.exp(-z))
    label = "высокая" if p >= 0.65 else "средняя" if p >= 0.4 else "низкая"
    return {"p": round(p, 3), "label": label}


# ------------------------------------------------------------------ объяснения

def _reasons(need: Need, cand: CandidateProfile, comp: dict, skill_details: list[dict], cond: dict, fsp: dict) -> list[dict]:
    r: list[dict] = []
    grade_name = GRADE_NAMES.get(cand.grade or "", "—")
    spec_name = SPEC_NAMES.get(cand.grade_specialization or "", "—")
    pct = round(100 * 0.5 * (1 + math.erf((cand.grade_theta or 0) / math.sqrt(2))))
    if spec_factor(need.specialization, cand.grade_specialization) >= 1 and cand.grade in need.grades:
        near = " (уровень у границы грейда)" if comp["category"] < 0.9 else ""
        r.append({"kind": "plus", "text": f"Категория «{spec_name} · {grade_name}» подтверждена тестом — результат выше, "
                                          f"чем у {pct}% кандидатов{near}"})
    else:
        why = []
        if spec_factor(need.specialization, cand.grade_specialization) < 1:
            why.append(f"смежная специализация «{spec_name}»")
        if cand.grade not in need.grades:
            why.append(f"грейд {grade_name} вне запрошенных")
        r.append({"kind": "info", "text": "Частичное совпадение категории: " + ", ".join(why) if why else "Частичное совпадение категории"})
    verified = [d["name"] for d in skill_details if d["status"] == "verified"]
    declared = [d["name"] for d in skill_details if d["status"] == "declared"]
    refuted = [d["name"] for d in skill_details if d["status"] == "refuted"]
    domain = [d["name"] for d in skill_details if d["status"] == "domain"]
    related = [f"{d['related']} вместо {d['name']}" for d in skill_details if d["status"] == "related"]
    missing = [d["name"] for d in skill_details if d["status"] == "missing" and d["required"]]
    if verified:
        r.append({"kind": "plus", "text": "Подтверждены тестом на уровне требований: " + ", ".join(verified)})
    if domain:
        r.append({"kind": "plus", "text": "Сильный результат в профильном домене теста: " + ", ".join(domain)})
    if declared:
        r.append({"kind": "info", "text": "Заявлены в профиле, но не проверены тестом: " + ", ".join(declared)})
    if refuted:
        r.append({"kind": "minus", "text": "Заявлены, но тест показал уровень ниже требуемого: " + ", ".join(refuted)})
    if related:
        r.append({"kind": "info", "text": "Смежный опыт: " + "; ".join(related)})
    if missing:
        r.append({"kind": "minus", "text": "Нет данных об обязательных навыках: " + ", ".join(missing)})
    top_domains = sorted((cand.domain_scores or {}).items(), key=lambda kv: -kv[1].get("score", 0))[:2]
    if top_domains and top_domains[0][1].get("score", 0) >= 0.7:
        r.append({"kind": "plus", "text": "Сильнейшие домены теста: " + ", ".join(
            f"{DOMAINS.get(d, d)} ({round(v['score'] * 100)}%)" for d, v in top_domains)})
    if fsp["linked"] and fsp["achievements"]:
        best = fsp["best"]
        r.append({"kind": "plus", "text": f"ФСП: {fsp['headline']}. Лучший результат — {best['event']} "
                                          f"({best['place_label']}, {best['date'][:4]})"})
    elif fsp["linked"]:
        r.append({"kind": "info", "text": "ФСП ID привязан, достижений в реестре пока нет"})
    else:
        r.append({"kind": "info", "text": "Нет истории ФСП — на попадание в подборку не влияет, бонус не начислен"})
    if cand.tasks_done:
        r.append({"kind": "plus", "text": f"Решено заданий работодателей: {cand.tasks_done} (профиль актуален)"})
    s = cond["salary_status"]
    if s == "fits":
        r.append({"kind": "plus", "text": "Ожидания по доходу укладываются в вилку"})
    elif s == "slightly_above":
        r.append({"kind": "minus", "text": "Ожидания по доходу немного выше вилки (до 15%)"})
    elif s == "above":
        r.append({"kind": "minus", "text": "Ожидания по доходу заметно выше вилки"})
    if cond["format"] < 0.5:
        r.append({"kind": "minus", "text": f"Предпочитает другой формат работы ({', '.join(WORK_FORMATS.get(f, f) for f in cand.work_formats or [])})"})
    if cond["city"] < 0.5:
        r.append({"kind": "minus", "text": f"Другой город ({cand.city}) и не готов к переезду"})
    elif cond["city"] < 1 and need.work_format != "remote":
        r.append({"kind": "info", "text": f"Готов к релокации из города {cand.city}"})
    return r


# ------------------------------------------------------------------ подбор

def base_pool_query():
    return (select(CandidateProfile).join(User, User.id == CandidateProfile.user_id)
            .where(User.is_active.is_(True), CandidateProfile.grade.is_not(None),
                   CandidateProfile.consent_publish.is_(True)))


def visible(cand: CandidateProfile) -> bool:
    return bool((cand.privacy or {}).get("visible_in_search", True))


def pool_profiles(db: Session, specs: set[str] | None = None) -> list:
    """Пул подбора: основные резюме (профили) и дополнительные резюме с категорией по тесту — только кандидаты,
    давшие согласие на публикацию и не скрывшие профиль. specs — фильтр по специализации категории."""
    q = base_pool_query()
    if specs is not None:
        q = q.where(CandidateProfile.grade_specialization.in_(specs))
    out: list = [c for c in db.scalars(q) if visible(c)]
    rq = (select(CandidateResume, CandidateProfile).join(CandidateProfile, CandidateProfile.id == CandidateResume.candidate_id)
          .join(User, User.id == CandidateProfile.user_id)
          .where(User.is_active.is_(True), CandidateProfile.consent_publish.is_(True), CandidateResume.visible.is_(True),
                 CandidateResume.grade.is_not(None)))
    if specs is not None:
        rq = rq.where(CandidateResume.grade_specialization.in_(specs))
    out += [ResumeView(c, r) for r, c in db.execute(rq) if visible(c)]
    return out


def best_per_candidate(results: list[dict]) -> list[dict]:
    """Кандидат с несколькими резюме попадает в выдачу один раз — с лучшим по соответствию резюме."""
    seen: set[int] = set()
    out = []
    for r in sorted(results, key=lambda x: -x["score"]):
        if r["candidate_id"] not in seen:
            seen.add(r["candidate_id"])
            out.append(r)
    return out


def score_candidates(need: Need, cands: list[CandidateProfile]) -> list[dict]:
    sims = text_similarities(need, cands)
    out = []
    for cand, sim in zip(cands, sims, strict=True):
        sk, skill_details = skills_component(need, cand)
        cond_v, cond = conditions_component(need, cand)
        sf = spec_factor(need.specialization, cand.grade_specialization)
        gf = grade_fit(need.grades, cand.grade)
        pb = band_probability(need.grades, cand)
        comp = {
            "skills": round(sk, 4),
            "strength": round(strength_for(cand, need.grades), 4),
            "category": round(sf * (gf if pb is None else 0.5 * gf + 0.5 * pb), 4),
            "conditions": round(cond_v, 4),
            "text": round(sim, 4),
        }
        score = sum(WEIGHTS[k] * v for k, v in comp.items()) * cond["availability"]
        if need.require_fsp and not cand.fsp_id:
            score *= 0.85  # работодатель отметил важность ФСП — мягкое понижение, а не исключение
        fsp = fsp_summary(cand.fsp_profile, cand.grade_specialization)
        out.append({
            "candidate_id": cand.id,
            "public_id": cand.public_id,
            "resume_id": cand.resume_id or 0,
            "resume_title": cand.headline,
            "score": round(score, 4),
            "match": round(score * 100),
            "components": comp,
            "skills": skill_details,
            "reasons": _reasons(need, cand, comp, skill_details, cond, fsp),
            "likelihood": response_likelihood(need, cand, cond),
            # срез атрибутов для фильтрации сохранённой подборки без пересчёта
            "specialization": cand.grade_specialization,
            "grade": cand.grade,
            "declared_skills": cand.skills or [],
            "verified_skills": cand.verified_skills or [],
            "has_fsp": bool(fsp["achievements"]),
            "fsp_linked": bool(cand.fsp_id),
            "work_formats": cand.work_formats or [],
            "city": cand.city,
            "relocation": cand.relocation,
            "desired_salary": cand.desired_salary,
            "strength": cand.strength,
        })
    out.sort(key=lambda x: -x["score"])
    return out


def recommend_categories(db: Session, need: Need) -> list[dict]:
    pairs: dict[tuple[str, str], float] = {}
    for g in need.grades:
        pairs[(need.specialization, g)] = 1.0
    lo = min(GRADE_INDEX[g] for g in need.grades)
    hi = max(GRADE_INDEX[g] for g in need.grades)
    if lo > 0:
        pairs.setdefault((need.specialization, GRADE_CODES[lo - 1]), 0.45)
    if hi < len(GRADE_CODES) - 1:
        pairs.setdefault((need.specialization, GRADE_CODES[hi + 1]), 0.6)
    for rel, f in RELATED_SPECS.get(need.specialization, {}).items():
        for g in need.grades:
            pairs.setdefault((rel, g), f)
    cands = pool_profiles(db, {p[0] for p in pairs})
    out = []
    for (spec, g), rel in sorted(pairs.items(), key=lambda kv: -kv[1]):
        group = [c for c in cands if c.grade_specialization == spec and c.grade == g]
        salaries = sorted(c.desired_salary for c in group if c.desired_salary)
        med = salaries[len(salaries) // 2] if salaries else None
        in_budget = (sum(1 for s in salaries if need.salary_to and s <= need.salary_to) / len(salaries)) if salaries else None
        out.append({
            "specialization": spec, "specialization_name": SPEC_NAMES[spec], "grade": g, "grade_name": GRADE_NAMES[g],
            "relevance": rel, "primary": rel >= 1.0, "count": len(group),
            "with_fsp": sum(1 for c in group if c.fsp_profile and c.fsp_profile.get("achievements")),
            "avg_strength": round(sum(c.strength for c in group) / len(group), 3) if group else None,
            "median_salary": med, "share_in_budget": None if in_budget is None else round(in_budget, 2),
            "open_to_offers": sum(1 for c in group if c.open_to_offers),
        })
    return out


def match(db: Session, need: Need, limit: int = 150) -> dict:
    cats = recommend_categories(db, need)
    allowed = {(c["specialization"], c["grade"]) for c in cats}
    pool = [c for c in pool_profiles(db, {p[0] for p in allowed}) if (c.grade_specialization, c.grade) in allowed]
    results = best_per_candidate(score_candidates(need, pool))[:limit]
    return {"categories": cats, "results": results, "pool_size": len({c.id for c in pool})}


def apply_filters(results: list[dict], f: dict) -> list[dict]:
    """Уточнение сохранённой подборки без пересчёта и без потери исходного результата."""
    out = []
    skills = set(f.get("skills") or [])
    for r in results:
        if f.get("specialization") and r["specialization"] != f["specialization"]:
            continue
        if f.get("grades") and r["grade"] not in f["grades"]:
            continue
        if skills:
            pool = set(r["verified_skills"]) if f.get("verified_only") else set(r["verified_skills"]) | set(r["declared_skills"])
            if not skills <= pool:
                continue
        if f.get("has_fsp") and not r["has_fsp"]:
            continue
        if f.get("work_format") and f["work_format"] not in (r["work_formats"] or [f["work_format"]]):
            continue
        if f.get("city") and (r["city"] or "").lower() != f["city"].lower() and not (f.get("allow_relocation") and r["relocation"]):
            continue
        if f.get("salary_max") and r["desired_salary"] and r["desired_salary"] > f["salary_max"]:
            continue
        if f.get("min_match") and r["match"] < f["min_match"]:
            continue
        out.append(r)
    return out
