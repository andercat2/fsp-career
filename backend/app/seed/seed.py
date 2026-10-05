"""Наполнение демонстрационными данными (выполняется при первом старте, если БД пуста).

Учётные записи для проверки (пароль у всех — demo12345):
  candidate@demo.ru — кандидат с двумя резюме и двумя категориями (Backend · Middle, DevOps · Junior), ФСП,
                      приглашениями и откликами;
  newbie@demo.ru    — новый кандидат без опроса и теста (для живой демонстрации сквозного сценария);
  employer@demo.ru  — работодатель «ТехноПульс» с потребностями, подборками и приглашениями;
  admin@demo.ru     — администратор (статистика банка заданий).
"""
from __future__ import annotations

import dataclasses
import logging
import random
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.security import hash_password
from app.models import (
    Application,
    CandidateProfile,
    CandidateResume,
    Company,
    Consent,
    GradeHistory,
    Invitation,
    ItemStat,
    Notification,
    Selection,
    SurveyResponse,
    Task,
    TaskAssignment,
    TestResponse,
    TestSession,
    User,
    Vacancy,
)
from app.seed import vacancies_data as vd
from app.seed.fsp_data import generate_participants
from app.seed.synthetic import (
    LANG_TITLE,
    ROLE_TITLE,
    SynthCandidate,
    default_params,
    generate_population,
    simulate_assessment,
)
from app.services import interactions as ix
from app.services.candidates import new_public_id
from app.services.matching.profile import recompute_candidate
from app.services.matching.ranking import Need, match
from app.services.nlp.vacancy_parser import parse_need
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import DOMAINS, SPEC_BY_CODE, resolve_blueprint, theta_to_grade
from app.services.testing import irt
from app.services.testing.bank import REGISTRY

log = logging.getLogger("seed")
DEMO_PASSWORD = "demo12345"
EXTRA_RESUME_RATE = 0.08  # доля синтетических кандидатов со вторым резюме (второй категорией)
SECOND_SPEC = {"backend": "devops", "frontend": "fullstack", "fullstack": "frontend", "ml": "data_analyst",
               "data_analyst": "ml", "devops": "backend", "qa": "backend"}


def _ago(days: float) -> object:
    return utcnow() - timedelta(days=days)


def _user(db: Session, email: str, role: str, pwd_hash: str, demo: bool = True) -> User:
    u = User(email=email, password_hash=pwd_hash, role=role, email_verified=True, is_demo=demo,
             created_at=_ago(random.uniform(30, 200)))
    db.add(u)
    db.flush()
    db.add(Consent(user_id=u.id, kind="pd_processing", granted=True, user_agent="seed"))
    return u


def _store_sessions(db: Session, cand: CandidateProfile, sc: SynthCandidate, rng: random.Random,
                    resume_id: int | None = None) -> None:
    """Сохраняет симулированные сессии CAT как реальные записи и обновляет онлайн-статистику заданий."""
    t0 = _ago(rng.uniform(20, 120))
    for i, (target, state, res) in enumerate(sc.sessions):
        started = t0 + timedelta(hours=i * 2)
        sess = TestSession(token=secrets.token_urlsafe(16), candidate_id=cand.id, resume_id=resume_id, specialization=sc.spec,
                           language=sc.lang, target_grade=target, blueprint=state.blueprint, status="completed",
                           theta=res["theta"], se=res["se"], n_items=res["n_items"], n_correct=res["n_correct"],
                           result=res | {"assigned_grade": target if sc.grade == target else None},
                           started_at=started, finished_at=started + timedelta(minutes=25))
        db.add(sess)
        db.flush()
        for seq, x in enumerate(state.answered, start=1):
            fam = REGISTRY[x.family_id]
            db.add(TestResponse(session_id=sess.id, seq=seq, family_id=x.family_id, domain=x.domain,
                                variant_seed=f"{rng.getrandbits(64):016x}", scored=True,
                                payload={"topic": fam.topic, "domain_name": DOMAINS.get(x.domain), "kind": fam.kind,
                                         "time_limit": fam.time_limit, "irt": {"a": x.a, "b": x.b, "c": x.c}},
                                answer_key={}, answer=None, is_correct=x.correct, presented_at=started,
                                answered_at=started, time_ms=x.time_ms))
            st = db.get(ItemStat, x.family_id)
            if st:
                p = float(irt.prob(res["theta"], st.a, st.b, st.c))
                st.exposures += 1
                st.correct += int(x.correct)
                st.expected_correct += p
                st.expected_var += p * (1 - p)
                st.drift_z = (st.correct - st.expected_correct) / max(st.expected_var, 1e-9) ** 0.5
    if sc.grade:
        db.add(GradeHistory(candidate_id=cand.id, resume_id=resume_id, specialization=sc.spec, old_grade=None,
                            new_grade=sc.grade, theta=sc.theta_hat, created_at=t0 + timedelta(hours=1)))


def _extra_resume(db: Session, cand: CandidateProfile, sc: SynthCandidate, rng: random.Random, params: dict,
                  spec: str, domain_theta: dict[str, float] | None = None, claimed: str | None = None,
                  title: str | None = None, skills: list[str] | None = None,
                  salary: int | None = None) -> CandidateResume:
    """Второе резюме под смежную специализацию: свой опрос и своя симулированная аттестация. В общих доменах
    (например, Python у бэкенда и DevOps) способность та же, в новых — ниже основной."""
    sp = SPEC_BY_CODE[spec]
    lang = sc.lang if sc.lang in sp["languages"] else sp["languages"][0]
    bp = resolve_blueprint(spec, lang)
    if domain_theta is None:
        drop = rng.uniform(0.4, 1.2)
        domain_theta = {d: sc.domain_theta.get(d, sc.theta - drop + rng.gauss(0, 0.3)) for d in bp}
    theta = sum(w * domain_theta[d] for d, w in bp.items())
    claimed = claimed or theta_to_grade(theta + rng.gauss(0, 0.3))
    sc2 = dataclasses.replace(sc, spec=spec, lang=lang, theta=theta, grade_true=theta_to_grade(theta),
                              domain_theta=domain_theta, claimed_grade=claimed, theta_hat=None, se=None, grade=None,
                              domain_scores={}, attempts=[], sessions=[])
    simulate_assessment(sc2, rng, params)
    core = [s for s in sp["core_skills"] if s in SKILL_BY_ID]
    res = CandidateResume(
        candidate_id=cand.id, title=title or ROLE_TITLE[spec].format(lang=LANG_TITLE[lang]),
        skills=skills or list(dict.fromkeys(rng.sample(core, min(len(core), rng.randint(3, 5)))
                                            + [s for s in sc.declared_skills if s in core])),
        desired_salary=salary, specialization=spec, primary_language=lang, claimed_grade=sc2.claimed_grade,
        industries=[], survey_completed_at=_ago(rng.uniform(5, 40)), created_at=_ago(rng.uniform(5, 40)),
    )
    if sc2.grade:
        res.grade, res.grade_specialization = sc2.grade, spec
        res.grade_theta, res.grade_se, res.domain_scores = sc2.theta_hat, sc2.se, sc2.domain_scores
        res.grade_assigned_at = _ago(rng.uniform(2, 30))
    cand.resumes.append(res)
    db.flush()
    db.add(SurveyResponse(candidate_id=cand.id, resume_id=res.id, specialization=spec, claimed_grade=sc2.claimed_grade,
                          warnings=[], answers={"specialization": spec, "language": lang,
                                                "claimed_grade": sc2.claimed_grade},
                          created_at=res.survey_completed_at))
    _store_sessions(db, cand, sc2, rng, resume_id=res.id)
    return res


def _candidate_from_synth(db: Session, sc: SynthCandidate, email: str, pwd_hash: str, rng: random.Random,
                          participants_by_q: list[dict], used_fsp: set[str]) -> CandidateProfile:
    u = _user(db, email, "candidate", pwd_hash)
    cand = CandidateProfile(
        user_id=u.id, public_id=new_public_id(db), full_name=sc.full_name,
        phone=f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
        telegram=f"@{email.split('@')[0].replace('.', '_')}", contact_email=email, city=sc.city,
        relocation=sc.relocation, work_formats=sc.work_formats, desired_salary=sc.desired_salary, headline=sc.headline,
        about=sc.about, experience_years=sc.experience_years, experience=sc.experience, education=sc.education,
        skills=sc.declared_skills, roles=["developer"] + (["code_review"] if sc.theta > 0 else [])
        + (["mentoring"] if sc.theta > 1 else []), soft_skills=rng.sample(["teamwork", "communication", "responsibility",
                                                                           "learning", "initiative"], 2),
        industries=[], specialization=sc.spec, primary_language=sc.lang, claimed_grade=sc.claimed_grade,
        survey_completed_at=_ago(rng.uniform(25, 130)), consent_pd=True, consent_publish=rng.random() < 0.96,
        open_to_offers=sc.open_to_offers,
        privacy={"show_name": rng.random() < 0.3, "show_salary": rng.random() < 0.85, "show_companies": True,
                 "show_fsp": True, "visible_in_search": True, "hide_invites_below_salary": rng.random() < 0.1},
        last_active_at=_ago(rng.expovariate(1 / 12)), created_at=_ago(rng.uniform(30, 200)),
    )
    if sc.grade:
        cand.grade, cand.grade_specialization = sc.grade, sc.spec
        cand.grade_theta, cand.grade_se, cand.domain_scores = sc.theta_hat, sc.se, sc.domain_scores
        cand.grade_assigned_at = _ago(rng.uniform(5, 100))
    if sc.fsp_quality is not None and participants_by_q:
        best = min((p for p in participants_by_q if p["fsp_id"] not in used_fsp),
                   key=lambda p: abs(p["quality"] - sc.fsp_quality), default=None)
        if best:
            used_fsp.add(best["fsp_id"])
            cand.fsp_id = best["fsp_id"]
            cand.fsp_profile = {k: v for k, v in best.items() if k != "quality"}
            cand.fsp_linked_at = cand.fsp_synced_at = _ago(rng.uniform(1, 60))
    db.add(cand)
    db.flush()
    db.add(SurveyResponse(candidate_id=cand.id, specialization=sc.spec, claimed_grade=sc.claimed_grade, warnings=[],
                          answers={"specialization": sc.spec, "language": sc.lang, "claimed_grade": sc.claimed_grade},
                          created_at=cand.survey_completed_at))
    _store_sessions(db, cand, sc, rng)
    recompute_candidate(db, cand)
    return cand


def _demo_synth() -> SynthCandidate:
    """Демо-кандидат candidate@demo.ru: Python-бэкенд уровня Middle с призовым местом ФСП."""
    return SynthCandidate(
        idx=9999, spec="backend", lang="python", theta=0.62, grade_true="middle",
        domain_theta={d: 0.62 + (0.4 if d in ("python", "sql") else 0.0) for d in
                      ("algorithms", "python", "sql", "databases", "http_api", "architecture", "security", "linux", "cicd")},
        true_skills=["python", "fastapi", "django", "postgresql", "redis", "docker", "rest", "sql", "git", "kafka"],
        declared_skills=["python", "fastapi", "django", "postgresql", "redis", "docker", "rest", "sql", "git", "kafka",
                         "celery", "pytest"],
        claimed_grade="middle", inflated=False, full_name="Петров Иван", city="Казань", relocation=False,
        work_formats=["hybrid", "remote"], desired_salary=260_000, experience_years=3.5,
        headline="Python-разработчик (FastAPI, PostgreSQL)",
        about="Backend-разработчик: 3,5 года пишу сервисы на Python. Проектировал API платёжного шлюза, оптимизировал "
              "запросы к PostgreSQL, внедрял очереди на Kafka. Призёр Чемпионата России по спортивному программированию.",
        experience=[{"company": "ООО «Стрим Лаб»", "position": "Python-разработчик", "start": "2023-02", "end": None,
                     "description": "Сервис платежей на FastAPI, PostgreSQL, Redis, Kafka. Снизил p95 API с 480 до 120 мс."},
                    {"company": "ООО «Логос ИТ»", "position": "Junior Python-разработчик", "start": "2021-09",
                     "end": "2023-01", "description": "Django, REST API для CRM, интеграции с 1С."}],
        education=[{"title": "КФУ, Институт ВМиИТ, бакалавр «Программная инженерия», 2022"}], fsp_quality=0.8,
    )


def _add_extra_resumes(db: Session, pop: list[SynthCandidate], cands: list, params: dict) -> int:
    """Часть кандидатов развивается в двух направлениях: второе резюме — вторая категория. Отдельный генератор
    случайных чисел, чтобы не сдвигать остальные демо-данные."""
    rng_res = random.Random(77)
    added = 0
    for sc, cand in zip(pop, cands, strict=True):
        if rng_res.random() < EXTRA_RESUME_RATE and cand is not None:
            _extra_resume(db, cand, sc, rng_res, params, SECOND_SPEC[sc.spec])
            recompute_candidate(db, cand)
            added += 1
    db.flush()
    return added


def _demo_devops_resume(db: Session, demo_cand: CandidateProfile, demo: SynthCandidate, params: dict) -> None:
    """Второе резюме демо-кандидата: DevOps — общие домены (Python) на уровне основного, новые ниже."""
    devops_theta = {"linux": -0.15, "networks": -0.6, "containers": 0.05, "kubernetes": -0.9, "cicd": -0.05,
                    "observability": -0.7, "security": -0.35, "python": 1.02}
    seed = 1001
    for seed in range(1001, 1040):  # детерминированно подбираем прогон, подтверждающий Junior, — для предсказуемой демонстрации
        probe = dataclasses.replace(demo, spec="devops", lang="python", domain_theta=devops_theta, claimed_grade="junior",
                                    theta_hat=None, se=None, grade=None, domain_scores={}, attempts=[], sessions=[])
        simulate_assessment(probe, random.Random(seed), params)
        if probe.grade == "junior":
            break
    _extra_resume(db, demo_cand, demo, random.Random(seed), params, "devops", domain_theta=devops_theta,
                  claimed="junior", title="DevOps-инженер (Docker, CI/CD, Linux)", salary=210_000,
                  skills=["docker", "linux", "bash", "git", "gitlab_ci", "kubernetes", "prometheus", "python"])
    recompute_candidate(db, demo_cand)


def upgrade_demo_data(db: Session) -> None:
    """Дозаполняет уже развёрнутый стенд демо-данными новых возможностей (идемпотентно): вторые резюме
    синтетических кандидатов и DevOps-резюме демо-кандидата — те же, что создаёт seed_if_empty на пустой БД."""
    from app.core.config import settings

    if db.scalar(select(CandidateResume.id).limit(1)) is not None:
        return
    demo_user = db.scalar(select(User).where(User.email == "candidate@demo.ru"))
    if demo_user is None or demo_user.candidate is None:
        return
    params = default_params()
    pop = generate_population(settings.seed_candidates, seed=7)
    by_email = {u.email: u.candidate for u in db.scalars(select(User).where(User.email.like("%@synthetic.example")))}
    added = _add_extra_resumes(db, pop, [by_email.get(f"cand{sc.idx:03d}@synthetic.example") for sc in pop], params)
    _demo_devops_resume(db, demo_user.candidate, _demo_synth(), params)
    db.commit()
    log.info("Демо-данные дополнены: вторые резюме у %d кандидатов и у демо-кандидата", added)


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    from app.core.config import settings

    log.info("Наполнение демо-данными…")
    rng = random.Random(20261005)
    random.seed(20261005)
    pwd = hash_password(DEMO_PASSWORD)
    params = default_params()

    # --- реестр ФСП (те же данные отдаёт fsp-mock)
    participants = [p for p in generate_participants() if not p["fsp_id"].startswith("FSP-DEMO")]
    used_fsp: set[str] = set()

    # --- администратор
    _user(db, "admin@demo.ru", "admin", pwd)

    # --- синтетические кандидаты
    pop = generate_population(settings.seed_candidates, seed=7)
    cands: list[CandidateProfile] = []
    for sc in pop:
        simulate_assessment(sc, rng, params)
        cands.append(_candidate_from_synth(db, sc, f"cand{sc.idx:03d}@synthetic.example", pwd, rng, participants,
                                           used_fsp))
    db.flush()
    _add_extra_resumes(db, pop, cands, params)

    # --- демо-кандидат с полной историей
    demo = _demo_synth()
    simulate_assessment(demo, random.Random(5), params)
    if demo.grade != "middle":  # для предсказуемой демонстрации фиксируем результат уровня Middle
        demo.sessions = demo.sessions[-1:]
        demo.grade, demo.theta_hat, demo.se, demo.domain_scores = "middle", 0.58, 0.29, demo.sessions[-1][2]["domains"]
    demo_cand = _candidate_from_synth(db, demo, "candidate@demo.ru", pwd, rng, participants, used_fsp)
    demo_cand.phone, demo_cand.telegram = "+7 917 000-12-34", "@ivan_petrov_dev"
    demo_cand.consent_publish, demo_cand.open_to_offers = True, True
    demo_cand.privacy = {**demo_cand.privacy, "visible_in_search": True, "hide_invites_below_salary": False}
    db.get(User, demo_cand.user_id).is_demo = True
    _demo_devops_resume(db, demo_cand, demo, params)

    # --- новый кандидат для живой демонстрации
    u = _user(db, "newbie@demo.ru", "candidate", pwd)
    db.add(CandidateProfile(user_id=u.id, public_id=new_public_id(db), contact_email="newbie@demo.ru", consent_pd=True,
                            full_name="Демидова Алиса", city="Казань"))

    # --- работодатели и вакансии
    companies: dict[str, Company] = {}
    for c in vd.COMPANIES:
        cu = _user(db, c["email"], "employer", pwd)
        comp = Company(owner_user_id=cu.id, name=c["name"], description=c["description"], industry=c["industry"],
                       city=c["city"], size=c["size"], website=c["website"], contact_name=c["contact_name"],
                       contact_email=c["email"], contact_telegram=c["contact_telegram"], contact_phone=c["contact_phone"],
                       domain_verified=c["email"].split("@")[1] == c["website"], trust_score=0.7)
        db.add(comp)
        db.flush()
        companies[c["key"]] = comp
    vacancies: list[Vacancy] = []
    for v in vd.VACANCIES:
        p = parse_need(v["text"], v["title"])
        lang = p["language"]
        vac = Vacancy(company_id=companies[v["company"]].id, title=v["title"], description=v["text"],
                      team_description=v["team"] or None, specialization=p["specialization"], grades=p["grades"],
                      must_skills=p["must_skills"], nice_skills=p["nice_skills"],
                      language=lang if lang in SPEC_BY_CODE[p["specialization"]]["languages"] else None,
                      work_format=p["work_format"] or "hybrid", city=p["city"] or companies[v["company"]].city,
                      salary_from=p["salary_from"] or 150_000, salary_to=p["salary_to"] or 250_000,
                      require_fsp=p["require_fsp"], is_published=v["published"], parsed=p,
                      created_at=_ago(rng.uniform(2, 25)))
        db.add(vac)
        vacancies.append(vac)
    db.flush()

    # --- приглашения: демо-работодатель приглашает лучших кандидатов по своим потребностям
    tp = companies["technopulse"]
    statuses = ["accepted", "accepted", "declined", "viewed", "sent", "sent", "expired", "accepted", "declined", "viewed"]
    reasons = ["salary", "format", "stack", "not_looking"]
    for vac in [v for v in vacancies if v.company_id == tp.id][:3]:
        need = ix.need_from_vacancy(vac)
        m = match(db, need, limit=12)
        for k, r in enumerate(m["results"][:6]):
            cand = db.get(CandidateProfile, r["candidate_id"])
            if cand.id == demo_cand.id:
                continue
            st = statuses[(k + vac.id) % len(statuses)]
            created = _ago(rng.uniform(1, 12))
            inv = Invitation(company_id=tp.id, candidate_id=cand.id, vacancy_id=vac.id, title=vac.title,
                             message=f"Здравствуйте! Нам понравился ваш профиль: {r['reasons'][0]['text'].lower()}. "
                                     f"Приглашаем обсудить позицию «{vac.title}».",
                             salary_from=vac.salary_from, salary_to=vac.salary_to, work_format=vac.work_format,
                             contact_method="Telegram: @technopulse_hr", status=st, match_score=r["score"],
                             match_snapshot={"reasons": r["reasons"], "components": r["components"]},
                             created_at=created, expires_at=created + timedelta(days=14))
            if st in ("viewed", "accepted", "declined"):
                inv.viewed_at = created + timedelta(hours=rng.uniform(1, 20))
            if st in ("accepted", "declined"):
                inv.responded_at = inv.viewed_at + timedelta(hours=rng.uniform(1, 30))
            if st == "declined":
                inv.decline_reason = rng.choice(reasons)
            if st == "expired":
                inv.created_at, inv.expires_at = _ago(20), _ago(6)
            db.add(inv)

    # --- приглашения демо-кандидату от разных компаний
    def invite_demo(comp_key: str, vac_idx: int | None, title: str, msg: str, s_from: int, s_to: int, status: str,
                    days: float):
        comp = companies[comp_key]
        vac = vacancies[vac_idx] if vac_idx is not None else None
        created = _ago(days)
        need = ix.need_from_vacancy(vac) if vac else Need(specialization="backend", grades=["middle"], must_skills=[],
                                                          nice_skills=[], salary_from=s_from, salary_to=s_to)
        from app.services.matching.ranking import score_candidates

        r = score_candidates(need, [demo_cand])[0]
        inv = Invitation(company_id=comp.id, candidate_id=demo_cand.id, vacancy_id=vac.id if vac else None, title=title,
                         message=msg, salary_from=s_from, salary_to=s_to, work_format=vac.work_format if vac else "remote",
                         contact_method=f"Telegram: {comp.contact_telegram}", status=status, match_score=r["score"],
                         match_snapshot={"reasons": r["reasons"], "components": r["components"]}, created_at=created,
                         expires_at=created + timedelta(days=14))
        if status != "sent":
            inv.viewed_at = created + timedelta(hours=3)
        if status == "accepted":
            inv.responded_at = created + timedelta(hours=5)
        db.add(inv)

    invite_demo("fintechlab", 4, "Go-разработчик в кредитный конвейер",
                "Иван, видим сильный результат теста по SQL и Python и призовое место на чемпионате ФСП. Готовы "
                "рассмотреть переход на Go с обучением в команде — первые 2 месяца с ментором.", 280_000, 340_000, "sent", 0.5)
    invite_demo("technopulse", 0, "Middle Python-разработчик (платёжный сервис)",
                "Добрый день! Ваш опыт с платёжным API и Kafka очень близок к нашим задачам. Офис в Казани, гибрид.",
                250_000, 320_000, "viewed", 2)
    invite_demo("logistics", None, "Python-разработчик (сервисы маршрутизации)",
                "Здравствуйте! Развиваем сервис построения маршрутов. Удалённо, можно частично.", 230_000, 270_000,
                "accepted", 9)

    # --- отклики синтетических кандидатов на опубликованные вакансии
    published = [v for v in vacancies if v.is_published]
    app_statuses = ["sent", "sent", "viewed", "accepted", "rejected"]
    for vac in published:
        same = [c for c in cands if c.grade_specialization == vac.specialization and c.grade]
        for cand in rng.sample(same, min(len(same), rng.randint(2, 5))):
            sc = ix.pair_score(vac, cand)
            db.add(Application(candidate_id=cand.id, vacancy_id=vac.id, status=rng.choice(app_statuses),
                               cover_letter="Здравствуйте! Интересна ваша вакансия, мой профиль и результаты теста — в "
                                            "карточке. Готов выполнить тестовое задание.",
                               match_score=sc["score"] if sc else None, created_at=_ago(rng.uniform(0.5, 10))))
    sc = ix.pair_score(vacancies[6], demo_cand)
    db.add(Application(candidate_id=demo_cand.id, vacancy_id=vacancies[6].id, status="viewed",
                       cover_letter="Хочу попробовать себя в fullstack: React изучаю, бэкенд — моя сильная сторона.",
                       match_score=sc["score"] if sc else None, created_at=_ago(4)))

    # --- регулярные задания
    tasks = []
    for t in vd.TASKS:
        task = Task(company_id=companies[t["company"]].id, title=t["title"], description=t["description"],
                    specialization=t["specialization"], grades=t["grades"], kind=t["kind"],
                    expected_answer=t["expected_answer"], time_estimate_min=t["time_estimate_min"],
                    created_at=_ago(rng.uniform(10, 40)))
        db.add(task)
        tasks.append(task)
    db.flush()
    answers_pool = [
        "Предлагаю хранить ключ идемпотентности и использовать уникальный индекс, обработку делать в транзакции, "
        "повторный запрос возвращает сохранённый результат.",
        "Сначала профилирование и метрики, затем кеширование, очередь и ретраи с экспоненциальной задержкой, "
        "мониторинг и алерты.",
        "Разбить задачу на этапы: диагностика, гипотезы, эксперимент, замер результата и откат при деградации.",
    ]
    for task in tasks:
        pool = [c for c in cands if c.grade_specialization == task.specialization and c.grade]
        for cand in rng.sample(pool, min(len(pool), 6)):
            ta = TaskAssignment(task_id=task.id, candidate_id=cand.id, offered_at=_ago(rng.uniform(8, 30)))
            roll = rng.random()
            if roll < 0.65:
                ta.status, ta.answer = "submitted", rng.choice(answers_pool)
                ta.submitted_at = ta.offered_at + timedelta(days=rng.uniform(0.5, 4))
                ta.auto_score = ix.auto_score(task, ta.answer)
                if roll < 0.45:
                    q = cand.grade_theta or 0
                    ta.status, ta.score = "reviewed", max(1, min(5, round(3 + q + rng.gauss(0, 0.7))))
                    ta.reviewed_at = ta.submitted_at + timedelta(days=1)
                    ta.feedback = rng.choice(["Хороший структурированный ответ.", "Не хватает деталей про отказоустойчивость.",
                                              "Отличное решение, обсудим на интервью."])
            elif roll < 0.8:
                ta.status = "skipped"
            db.add(ta)
            db.flush()
            if ta.status == "reviewed":
                ix.apply_task_review(db, ta)
    demo_task = TaskAssignment(task_id=tasks[0].id, candidate_id=demo_cand.id, offered_at=_ago(1),
                               due_at=utcnow() + timedelta(days=6))
    db.add(demo_task)
    done = TaskAssignment(task_id=tasks[3].id, candidate_id=demo_cand.id, offered_at=_ago(15), status="reviewed",
                          answer="Token bucket в Redis на Lua-скрипте, общий для всех подов, очередь заявок с приоритетами, "
                                 "ретраи с backoff и circuit breaker при ошибках бюро, метрики отклонённых запросов.",
                          submitted_at=_ago(14), reviewed_at=_ago(13), score=5,
                          feedback="Отлично: учли гонки между подами и деградацию бюро.")
    db.add(done)
    db.flush()
    ix.apply_task_review(db, done)

    # --- сохранённая подборка для демо-работодателя
    v0 = vacancies[0]
    m = match(db, ix.need_from_vacancy(v0))
    db.add(Selection(company_id=tp.id, vacancy_id=v0.id, title=v0.title, need=ix.need_from_vacancy(v0).to_dict(),
                     categories=m["categories"], results=m["results"], created_at=_ago(1)))

    # --- уведомления
    db.add(Notification(user_id=demo_cand.user_id, kind="invitation_new", title="Приглашение от Финтех Лаб",
                        body="«Go-разработчик в кредитный конвейер», 280 000–340 000 ₽", link="/candidate/invitations"))
    db.add(Notification(user_id=demo_cand.user_id, kind="task_new", title="Новое задание от ТехноПульс",
                        body="«Идемпотентность приёма платежей» — предложите подход", link="/candidate/tasks"))
    db.add(Notification(user_id=tp.owner_user_id, kind="invitation_accepted", title="Кандидат принял приглашение",
                        body="Контакты кандидата открыты в карточке", link="/employer/invitations"))
    db.commit()
    graded = sum(1 for c in cands if c.grade)
    log.info("Демо-данные готовы: %d кандидатов (%d с категорией), %d вакансий", len(cands) + 2, graded, len(vacancies))
