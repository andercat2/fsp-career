"""Синтетическая популяция кандидатов с известной «латентной истиной».

У каждого кандидата есть истинный уровень θ, истинные навыки и доменные способности. Наблюдаемые данные
(резюме) шумные: ~35% кандидатов завышают грейд и добавляют «модные» навыки, которых не знают. Тест симулируется
моделью IRT из истинных доменных способностей. Это позволяет честно измерить, насколько выдача, построенная на
тестах, лучше выдачи по самоописанию (см. validation/).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from app.seed.fsp_data import person_name
from app.services.reference.skills import SKILL_BY_ID, skills_for_spec
from app.services.reference.taxonomy import (
    GRADE_CODES,
    GRADE_INDEX,
    SPEC_BY_CODE,
    resolve_blueprint,
    theta_to_grade,
)
from app.services.testing import irt
from app.services.testing.bank import REGISTRY
from app.services.testing.cat import AnsweredItem, CatConfig, CatState, ItemState, decide, select_next, should_stop

SPEC_DIST = [("backend", 0.27), ("frontend", 0.18), ("fullstack", 0.10), ("ml", 0.10), ("data_analyst", 0.12),
             ("devops", 0.10), ("qa", 0.13)]
CITY_DIST = [("Москва", 0.34), ("Санкт-Петербург", 0.15), ("Казань", 0.08), ("Новосибирск", 0.06),
             ("Екатеринбург", 0.06), ("Нижний Новгород", 0.05), ("Томск", 0.04), ("Иннополис", 0.03),
             ("Самара", 0.04), ("Краснодар", 0.04), ("Пермь", 0.03), ("Уфа", 0.03), ("Воронеж", 0.03),
             ("Владивосток", 0.02)]
BASE_SALARY = {"intern": 65_000, "junior": 115_000, "middle": 215_000, "senior": 340_000}
SPEC_SALARY = {"ml": 1.15, "devops": 1.10, "backend": 1.05, "fullstack": 1.05, "frontend": 1.0, "data_analyst": 0.9,
               "qa": 0.85}
ROLE_TITLE = {"backend": "{lang}-разработчик", "frontend": "Frontend-разработчик", "fullstack": "Fullstack-разработчик",
              "ml": "Data Scientist", "data_analyst": "Аналитик данных", "devops": "DevOps-инженер", "qa": "QA-инженер"}
LANG_TITLE = {"python": "Python", "java": "Java", "go": "Go", "javascript": "Node.js"}
COMPANIES = ["Альфа Софт", "Неосистемы", "Стрим Лаб", "Цифровой Город", "ДатаКрафт", "Волна Технологии", "Терминал",
             "Логос ИТ", "Северный Код", "Пиксель Плюс", "Облачные решения", "ИнфоТех", "Маркет Лайн", "Телеком Сервис"]
UNIVERSITIES = ["КФУ, Институт ВМиИТ, бакалавр", "ИТМО, магистр", "МФТИ, бакалавр", "НИУ ВШЭ, ФКН, бакалавр",
                "МГТУ им. Н. Э. Баумана, специалист", "УрФУ, бакалавр", "НГУ, магистр", "ТПУ, бакалавр",
                "Университет Иннополис, бакалавр", "СПбГУ, бакалавр", "ННГУ, магистр", "Самарский университет, бакалавр"]
BUZZWORDS = {
    "backend": ["kafka", "kubernetes", "microservices", "grpc", "system_design", "clickhouse"],
    "frontend": ["typescript", "redux", "web_perf", "graphql", "a11y", "jest"],
    "fullstack": ["kubernetes", "graphql", "microservices", "redux", "docker"],
    "ml": ["pytorch", "nlp", "mlops", "cv", "spark", "gradient_boosting"],
    "data_analyst": ["ab_testing", "spark", "dwh", "python", "scikit_learn"],
    "devops": ["kubernetes", "terraform", "sre", "cloud", "elk"],
    "qa": ["selenium", "load_testing", "api_testing", "pytest", "mobile_testing"],
}
ABOUT_TEMPLATES = [
    "Занимаюсь {area}. В работе использую {skills}. {extra}",
    "{area_cap} — моя основная специализация. Стек: {skills}. {extra}",
    "Опыт в {area}: {skills}. {extra}",
]
AREA = {"backend": "серверной разработкой и проектированием API", "frontend": "разработкой интерфейсов веб-приложений",
        "fullstack": "полным циклом веб-разработки", "ml": "машинным обучением и анализом данных",
        "data_analyst": "продуктовой аналитикой и отчётностью", "devops": "инфраструктурой, CI/CD и эксплуатацией",
        "qa": "тестированием веб- и мобильных приложений"}
EXTRA = ["Люблю разбираться в сложных задачах.", "Участвую в код-ревью и менторю стажёров.",
         "Интересны высоконагруженные системы.", "Готов к новым вызовам.", "Стремлюсь к чистому коду и тестам.",
         "Участвовал в хакатонах.", "Ищу команду с сильной инженерной культурой.", ""]


def _pick(rng: random.Random, dist):
    r, acc = rng.random(), 0.0
    for v, p in dist:
        acc += p
        if r <= acc:
            return v
    return dist[-1][0]


@dataclass
class SynthCandidate:
    idx: int
    spec: str
    lang: str
    theta: float
    grade_true: str
    domain_theta: dict[str, float]
    true_skills: list[str]
    declared_skills: list[str]
    claimed_grade: str
    inflated: bool
    full_name: str
    city: str
    relocation: bool
    work_formats: list[str]
    desired_salary: int
    experience_years: float
    headline: str
    about: str
    experience: list[dict]
    education: list[dict]
    fsp_quality: float | None = None
    open_to_offers: bool = True
    # результаты симулированной аттестации
    theta_hat: float | None = None
    se: float | None = None
    grade: str | None = None
    domain_scores: dict = field(default_factory=dict)
    attempts: list[dict] = field(default_factory=list)
    sessions: list[tuple] = field(default_factory=list)  # (target, CatState, result) — для сида БД


def generate_population(n: int, seed: int = 42, inflation_rate: float = 0.35) -> list[SynthCandidate]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        spec = _pick(rng, SPEC_DIST)
        sp = SPEC_BY_CODE[spec]
        lang = rng.choice(sp["languages"])
        theta = max(-2.6, min(2.6, rng.gauss(0, 1)))
        grade_true = theta_to_grade(theta)
        bp = resolve_blueprint(spec, lang)
        domain_theta = {d: theta + rng.gauss(0, 0.35) for d in bp}
        pool = [s.id for s in skills_for_spec(spec)]
        core = [s for s in sp["core_skills"] if s in SKILL_BY_ID]
        k = int(max(3, min(11, round(5 + 2.2 * theta + rng.gauss(0, 1)))))
        lang_skill = {"python": "python", "java": "java", "go": "go", "javascript": "javascript"}[lang]
        true_skills = list(dict.fromkeys([lang_skill] + rng.sample(core, min(len(core), max(2, k // 2)))
                                         + rng.sample(pool, min(len(pool), k))))[:k + 1]
        # навыки, не принадлежащие ни одному домену блюпринта, ослабляют доменную θ
        inflated = rng.random() < inflation_rate
        declared = [s for s in true_skills if rng.random() > 0.08]
        if inflated:
            extra = [s for s in BUZZWORDS[spec] if s not in true_skills and s in SKILL_BY_ID]
            declared += rng.sample(extra, min(len(extra), rng.randint(2, 4)))
        honest_claim = theta_to_grade(theta + rng.gauss(0, 0.3))
        claimed = GRADE_CODES[min(3, GRADE_INDEX[grade_true] + 1)] if inflated else honest_claim
        gi = GRADE_INDEX[grade_true]
        years = round(max(0.0, [rng.uniform(0, 1), rng.uniform(1, 2.5), rng.uniform(2, 5), rng.uniform(4.5, 10)][gi]
                          + (rng.uniform(0.5, 1.5) if inflated else 0)), 1)
        name, _ = person_name(rng)
        city = _pick(rng, CITY_DIST)
        formats = sorted(set(rng.sample(["office", "hybrid", "remote"], rng.randint(1, 3))))
        salary = BASE_SALARY[grade_true] * SPEC_SALARY[spec] * math.exp(rng.gauss(0, 0.15))
        if inflated:
            salary *= 1.15
        salary = int(round(salary / 5000) * 5000)
        title = ROLE_TITLE[spec].format(lang=LANG_TITLE[lang])
        skill_names = [SKILL_BY_ID[s].name for s in declared if s in SKILL_BY_ID]
        about = rng.choice(ABOUT_TEMPLATES).format(area=AREA[spec], area_cap=AREA[spec][0].upper() + AREA[spec][1:],
                                                   skills=", ".join(skill_names[:6]), extra=rng.choice(EXTRA)).strip()
        exp_entries = []
        remaining = years
        end_year = 2026
        while remaining > 0.3 and len(exp_entries) < 3:
            dur = min(remaining, rng.uniform(1, 3.5))
            start_year = int(end_year - dur)
            comp = rng.choice(COMPANIES)
            used = rng.sample(skill_names, min(len(skill_names), 3)) if skill_names else []
            exp_entries.append({
                "company": f"ООО «{comp}»", "position": title,
                "start": f"{start_year}-{rng.randint(1, 12):02d}",
                "end": None if not exp_entries else f"{end_year}-{rng.randint(1, 12):02d}",
                "description": f"{AREA[spec].capitalize()}: {', '.join(used)}." if used else AREA[spec].capitalize(),
            })
            remaining -= dur
            end_year = start_year
        fsp_q = None
        p_fsp = min(0.6, max(0.08, 0.27 + 0.13 * theta))
        if rng.random() < p_fsp:
            fsp_q = min(0.99, max(0.01, 0.5 + 0.22 * theta + rng.gauss(0, 0.15)))
        out.append(SynthCandidate(
            idx=i, spec=spec, lang=lang, theta=theta, grade_true=grade_true, domain_theta=domain_theta,
            true_skills=true_skills, declared_skills=list(dict.fromkeys(declared)), claimed_grade=claimed,
            inflated=inflated, full_name=name, city=city, relocation=rng.random() < 0.3, work_formats=formats,
            desired_salary=salary, experience_years=years, headline=title, about=about, experience=exp_entries,
            education=[{"title": rng.choice(UNIVERSITIES)}], fsp_quality=fsp_q, open_to_offers=rng.random() < 0.88,
        ))
    return out


def default_params() -> dict[str, ItemState]:
    return {f.id: ItemState(f.a, f.b, f.c) for f in REGISTRY.values()}


def simulate_cat(domain_theta: dict[str, float], spec: str, lang: str, target: str, rng: random.Random,
                 params: dict[str, ItemState], cfg: CatConfig | None = None, exclude: set[str] | None = None,
                 cheat_known: set[str] | None = None) -> tuple[CatState, dict]:
    """Один прогон адаптивного теста. cheat_known — семейства, ответы на которые кандидат «знает заранее»
    (модель утечки: для статичных заданий ответ известен, для параметрических — помогает лишь частично)."""
    cfg = cfg or CatConfig()
    bp = resolve_blueprint(spec, lang)
    state = CatState(bp, target, lang)
    while not should_stop(state, cfg):
        fam = select_next(state, params, rng, cfg, exclude=exclude)
        if fam is None:
            break
        th = domain_theta.get(fam.domain, sum(domain_theta.values()) / len(domain_theta))
        p = float(irt.prob(th, fam.a, fam.b, fam.c))
        if cheat_known and fam.id in cheat_known:
            p = 0.98 if not fam.parametric else p + (1 - p) * 0.25
        u = rng.random() < p
        state.answered.append(AnsweredItem(fam.id, fam.domain, fam.a, fam.b, fam.c, bool(u), True,
                                           int(rng.uniform(0.2, 0.9) * fam.time_limit * 1000), fam.time_limit, fam.level))
    return state, decide(state, cfg)


def simulate_assessment(c: SynthCandidate, rng: random.Random, params: dict[str, ItemState]) -> SynthCandidate:
    """Политика аттестации как в продукте: заявленный уровень → при неудаче уровнем ниже → при уверенном
    результате — попытка уровнем выше. Грейд не понижается, итог — максимальный подтверждённый уровень."""
    target = c.claimed_grade
    tried: set[str] = set()
    seen: set[str] = set()
    best: str | None = None
    last_state = None
    for _ in range(4):
        if target in tried:
            break
        tried.add(target)
        state, res = simulate_cat(c.domain_theta, c.spec, c.lang, target, rng, params, exclude=seen)
        seen |= {x.family_id for x in state.answered}
        c.attempts.append({"target": target, **{k: res[k] for k in ("decision", "theta", "se", "n_items")}})
        c.sessions.append((target, state, res))
        if res["decision"] in ("confirmed", "confirmed_strong"):
            if best is None or GRADE_INDEX[target] > GRADE_INDEX[best]:
                best, last_state = target, (state, res)
            if res["decision"] == "confirmed_strong" and res.get("next_grade"):
                target = res["next_grade"]
                continue
            break
        if best is not None:
            break
        nxt = res.get("suggested_grade")
        if not nxt:
            break
        target = nxt
    if last_state:
        state, res = last_state
        c.grade, c.theta_hat, c.se, c.domain_scores = best, res["theta"], res["se"], res["domains"]
    return c
