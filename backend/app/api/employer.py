"""Личный кабинет работодателя: компания, потребности/вакансии, подборки, банк кандидатов, приглашения,
отклики, регулярные задания."""
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import DB, EmployerCompany
from app.core.config import settings
from app.core.db import utcnow
from app.models import (
    Application,
    AuditLog,
    CandidateProfile,
    Invitation,
    Selection,
    ShortlistItem,
    Task,
    TaskAssignment,
    Vacancy,
)
from app.schemas import (
    ApplicationStatusIn,
    CodeTaskSpec,
    CompanyIn,
    InvitationIn,
    Message,
    NeedIn,
    ParseNeedIn,
    ShortlistIn,
    TaskIn,
    TaskReviewIn,
    VacancyIn,
)
from app.services import interactions as ix
from app.services.sandbox import tasks as code_tasks
from app.services.candidates import employer_view, percentile, privacy
from app.services.fsp.scoring import fsp_summary
from app.services.matching.ranking import (
    Need,
    apply_filters,
    match,
    pool_profiles,
    response_likelihood,
    score_candidates,
    visible,
)
from app.services.nlp.vacancy_parser import parse_need
from app.services.notify import audit, notify
from app.services.pdf.profile_pdf import render_profile_pdf
from app.services.reference.skills import SKILL_BY_ID
from app.services.reference.taxonomy import GRADE_CODES, GRADE_NAMES, SPEC_BY_CODE, SPEC_NAMES
from app.services.resumes import ResumeView
from app.services.testing.preview import vacancy_test_preview

router = APIRouter(prefix="/employer", tags=["Работодатель"])


# ------------------------------------------------------------------ компания

def _company_out(c) -> dict:
    return {k: getattr(c, k) for k in ("id", "name", "description", "industry", "website", "city", "size", "contact_name",
                                       "contact_email", "contact_phone", "contact_telegram", "domain_verified",
                                       "trust_score", "ats_webhook_url", "created_at")}


@router.get("/company", summary="Профиль компании")
def get_company(comp: EmployerCompany):
    return _company_out(comp)


@router.put("/company", summary="Обновить профиль компании")
def put_company(data: CompanyIn, comp: EmployerCompany, db: DB):
    for k, v in data.model_dump().items():
        setattr(comp, k, v)
    # Простейший сигнал добросовестности: корпоративный e-mail на домене сайта компании
    site = urlparse(comp.website if "://" in (comp.website or "") else f"https://{comp.website or ''}").hostname or ""
    mail_domain = (comp.contact_email or comp.owner.email).split("@")[-1].lower()
    comp.domain_verified = bool(site) and site.lower().removeprefix("www.").endswith(mail_domain)
    comp.trust_score = round(min(1.0, max(comp.trust_score, 0.5) + (0.2 if comp.domain_verified else 0.0)), 3)
    db.commit()
    return _company_out(comp)


@router.get("/dashboard", summary="Сводка работодателя")
def dashboard(comp: EmployerCompany, db: DB):
    invs = list(db.scalars(select(Invitation).where(Invitation.company_id == comp.id)))
    ix.expire_invitations(db, invs)
    by_status = {s: sum(1 for i in invs if i.status == s) for s in ix.INVITATION_STATUSES}
    responded = [i for i in invs if i.responded_at]
    hours = [(i.responded_at - i.created_at).total_seconds() / 3600 for i in responded]
    vac = list(db.scalars(select(Vacancy).where(Vacancy.company_id == comp.id, Vacancy.status == "active")))
    apps_new = db.scalar(select(func.count()).select_from(Application).join(Vacancy).where(
        Vacancy.company_id == comp.id, Application.status == "sent")) or 0
    subs = db.scalar(select(func.count()).select_from(TaskAssignment).join(Task).where(
        Task.company_id == comp.id, TaskAssignment.status == "submitted")) or 0
    decline_reasons: dict[str, int] = {}
    for i in invs:
        if i.decline_reason:
            decline_reasons[i.decline_reason] = decline_reasons.get(i.decline_reason, 0) + 1
    pool = len({c.id for c in pool_profiles(db)})  # кандидаты с категорией хотя бы по одному резюме
    return {
        "company": _company_out(comp),
        "invitations": {"total": len(invs), "by_status": by_status,
                        "acceptance_rate": round(by_status["accepted"] / len(responded), 3) if responded else None,
                        "avg_response_hours": round(sum(hours) / len(hours), 1) if hours else None,
                        "decline_reasons": decline_reasons},
        "vacancies_active": len(vac), "vacancies_published": sum(v.is_published for v in vac),
        "applications_new": apps_new, "task_submissions_pending": subs, "candidates_in_bank": pool,
    }


# ------------------------------------------------------------------ потребности / вакансии

def _own_vacancy(db, comp, vid: int) -> Vacancy:
    v = db.get(Vacancy, vid)
    if not v or v.company_id != comp.id:
        raise HTTPException(404, "Вакансия не найдена")
    return v


def _vacancy_out(db, v: Vacancy) -> dict:
    apps = db.scalar(select(func.count()).select_from(Application).where(Application.vacancy_id == v.id)) or 0
    invs = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.vacancy_id == v.id)) or 0
    return ix.vacancy_brief(v) | {
        "description": v.description, "team_description": v.team_description, "must_skills": v.must_skills,
        "nice_skills": v.nice_skills, "language": v.language, "employment": v.employment, "require_fsp": v.require_fsp,
        "parsed": v.parsed, "created_at": v.created_at, "updated_at": v.updated_at,
        "applications_count": apps, "invitations_count": invs,
        "must_skill_names": [SKILL_BY_ID[s].name for s in v.must_skills or [] if s in SKILL_BY_ID],
        "nice_skill_names": [SKILL_BY_ID[s].name for s in v.nice_skills or [] if s in SKILL_BY_ID],
    }


@router.post("/vacancies/parse", summary="Разобрать текст потребности (NLP): специализация, грейд, навыки, вилка")
def parse_vacancy(data: ParseNeedIn):
    r = parse_need(data.text, data.title)
    r["must_skill_names"] = [SKILL_BY_ID[s].name for s in r["must_skills"]]
    r["nice_skill_names"] = [SKILL_BY_ID[s].name for s in r["nice_skills"]]
    r["specialization_name"] = SPEC_NAMES[r["specialization"]]
    return r


@router.get("/vacancies", summary="Мои потребности и вакансии")
def list_vacancies(comp: EmployerCompany, db: DB):
    rows = db.scalars(select(Vacancy).where(Vacancy.company_id == comp.id).order_by(Vacancy.created_at.desc()))
    return [_vacancy_out(db, v) for v in rows]


def _validate_vacancy(data: VacancyIn) -> dict:
    payload = data.model_dump()
    if data.specialization not in SPEC_BY_CODE:
        raise HTTPException(422, "Неизвестная специализация")
    payload["must_skills"] = [s for s in dict.fromkeys(data.must_skills) if s in SKILL_BY_ID]
    payload["nice_skills"] = [s for s in dict.fromkeys(data.nice_skills) if s in SKILL_BY_ID and s not in payload["must_skills"]]
    langs = SPEC_BY_CODE[data.specialization]["languages"]
    payload["language"] = data.language if data.language in langs else langs[0]
    return payload


@router.post("/vacancies", status_code=201, summary="Создать потребность (приватно) или вакансию (опубликовать)")
def create_vacancy(data: VacancyIn, comp: EmployerCompany, db: DB):
    v = Vacancy(company_id=comp.id, **_validate_vacancy(data))
    db.add(v)
    db.commit()
    return _vacancy_out(db, v)


@router.get("/vacancies/{vid}", summary="Потребность/вакансия")
def get_vacancy(vid: int, comp: EmployerCompany, db: DB):
    return _vacancy_out(db, _own_vacancy(db, comp, vid))


@router.put("/vacancies/{vid}", summary="Редактировать потребность/вакансию")
def update_vacancy(vid: int, data: VacancyIn, comp: EmployerCompany, db: DB):
    v = _own_vacancy(db, comp, vid)
    for k, val in _validate_vacancy(data).items():
        setattr(v, k, val)
    db.commit()
    return _vacancy_out(db, v)


@router.post("/vacancies/{vid}/close", summary="Закрыть вакансию")
def close_vacancy(vid: int, comp: EmployerCompany, db: DB):
    v = _own_vacancy(db, comp, vid)
    v.status = "closed"
    v.is_published = False
    db.commit()
    return _vacancy_out(db, v)


@router.get("/vacancies/{vid}/test-preview", summary="Как по этой вакансии формируются задания теста")
def test_preview(vid: int, comp: EmployerCompany, db: DB, seed: int | None = None):
    return vacancy_test_preview(_own_vacancy(db, comp, vid), seed=seed)


@router.get("/vacancies/{vid}/applications", summary="Отклики на вакансию (с оценкой соответствия)")
def vacancy_applications(vid: int, comp: EmployerCompany, db: DB):
    v = _own_vacancy(db, comp, vid)
    apps = list(db.scalars(select(Application).where(Application.vacancy_id == v.id)))
    need = ix.need_from_vacancy(v)
    profs = {a.id: ix.application_profile(a) for a in apps}
    graded = [p for p in profs.values() if p.grade]
    scores = {(r["candidate_id"], r["resume_id"]): r for r in score_candidates(need, graded)}
    out = []
    for a in apps:
        p = profs[a.id]
        sc = scores.get((a.candidate_id, p.resume_id or 0))
        out.append({"id": a.id, "status": a.status, "status_name": ix.APPLICATION_STATUSES[a.status],
                    "cover_letter": a.cover_letter, "employer_comment": a.employer_comment, "created_at": a.created_at,
                    "candidate": _card(db, comp, p),
                    "match": sc["match"] if sc else None, "reasons": sc["reasons"] if sc else []})
    out.sort(key=lambda x: -(x["match"] or -1))
    return out


@router.put("/applications/{app_id}", summary="Изменить статус отклика")
def update_application(app_id: int, data: ApplicationStatusIn, comp: EmployerCompany, db: DB):
    a = db.get(Application, app_id)
    if not a or a.vacancy.company_id != comp.id:
        raise HTTPException(404, "Отклик не найден")
    if a.status == "withdrawn":
        raise HTTPException(409, "Кандидат отозвал отклик")
    a.status = data.status
    a.employer_comment = data.comment or a.employer_comment
    if data.status == "viewed" and not a.viewed_at:
        a.viewed_at = utcnow()
    if data.status in ("accepted", "rejected"):
        notify(db, a.candidate.user_id, "application_status", f"Отклик на «{a.vacancy.title}»: "
               f"{ix.APPLICATION_STATUSES[data.status].lower()}", data.comment, "/candidate/applications", email=True)
    db.commit()
    return {"id": a.id, "status": a.status, "status_name": ix.APPLICATION_STATUSES[a.status]}


# ------------------------------------------------------------------ подборки

def _card(db, comp, cand: CandidateProfile, extra: dict | None = None) -> dict:
    """cand — профиль (основное резюме) или ResumeView дополнительного резюме."""
    v = employer_view(db, cand, comp)
    pv = privacy(cand)
    return {
        "id": cand.id, "public_id": cand.public_id, "display_name": v["display_name"], "name_hidden": v["name_hidden"],
        "resume_id": cand.resume_id or 0, "categories": v["resumes"],
        "headline": cand.headline, "city": cand.city, "relocation": cand.relocation, "work_formats": cand.work_formats,
        "experience_years": cand.experience_years, "specialization": cand.grade_specialization,
        "specialization_name": SPEC_NAMES.get(cand.grade_specialization or ""), "grade": cand.grade,
        "grade_name": GRADE_NAMES.get(cand.grade or ""), "percentile": percentile(cand.grade_theta),
        "strength": round(cand.strength or 0, 3),
        "verified_skills": [SKILL_BY_ID[s].name for s in cand.verified_skills or [] if s in SKILL_BY_ID],
        "declared_skills": [SKILL_BY_ID[s].name for s in cand.skills or []
                            if s in SKILL_BY_ID and s not in (cand.verified_skills or [])],
        "fsp_headline": v["fsp"].get("headline"), "fsp_linked": bool(cand.fsp_id),
        "desired_salary": cand.desired_salary if pv["show_salary"] else None,
        "open_to_offers": cand.open_to_offers, "tasks_done": cand.tasks_done,
        "contacts_unlocked": v["contacts_unlocked"], **(extra or {}),
    }


def _company_relations(db, comp) -> tuple[dict[int, str], set[int]]:
    inv = {}
    for i in db.scalars(select(Invitation).where(Invitation.company_id == comp.id).order_by(Invitation.created_at)):
        inv[i.candidate_id] = i.status
    short = set(db.scalars(select(ShortlistItem.candidate_id).where(ShortlistItem.company_id == comp.id)))
    return inv, short


def _need_from_input(db, comp, data: NeedIn) -> tuple[Need, str, int | None, dict | None]:
    parsed = None
    if data.vacancy_id:
        v = _own_vacancy(db, comp, data.vacancy_id)
        need = ix.need_from_vacancy(v)
        title = v.title
    else:
        if not data.text and not data.specialization:
            raise HTTPException(422, "Опишите потребность текстом или укажите специализацию")
        parsed = parse_need(data.text or "", data.title or "") if data.text else None
        base = parsed or {}
        need = Need(
            specialization=data.specialization or base.get("specialization"),
            grades=data.grades or base.get("grades") or ["middle"],
            must_skills=data.must_skills if data.must_skills is not None else base.get("must_skills", []),
            nice_skills=data.nice_skills if data.nice_skills is not None else base.get("nice_skills", []),
            salary_from=data.salary_from or base.get("salary_from"), salary_to=data.salary_to or base.get("salary_to"),
            work_format=data.work_format or base.get("work_format"), city=data.city or base.get("city"),
            text=data.text or "", title=data.title or "",
            require_fsp=data.require_fsp if data.require_fsp is not None else base.get("require_fsp", False),
        )
        title = data.title or f"{SPEC_NAMES[need.specialization]} · {', '.join(GRADE_NAMES[g] for g in need.grades)}"
    if need.specialization not in SPEC_BY_CODE:
        raise HTTPException(422, "Не удалось определить специализацию — укажите её явно")
    return need, title, data.vacancy_id, parsed


def _selection_view(db, comp, sel: Selection, filters: dict, page: int, size: int) -> dict:
    results = apply_filters(sel.results, filters)
    total = len(results)
    chunk = results[(page - 1) * size: page * size]
    inv, short = _company_relations(db, comp)
    cands = {c.id: c for c in db.scalars(select(CandidateProfile).where(
        CandidateProfile.id.in_([r["candidate_id"] for r in chunk])))}
    rows = []
    for r in chunk:
        c = cands.get(r["candidate_id"])
        if c is None or not visible(c):
            continue
        rid = r.get("resume_id") or 0
        res = next((x for x in c.resumes if x.id == rid and x.visible), None) if rid else None
        if rid and res is None:  # кандидат скрыл или удалил это резюме после формирования подборки
            continue
        rows.append(_card(db, comp, ResumeView(c, res) if res else c, {
            "match": r["match"], "score": r["score"], "components": r["components"], "reasons": r["reasons"],
            "skills_match": r["skills"], "likelihood": r["likelihood"],
            "invitation_status": inv.get(c.id), "shortlisted": c.id in short,
        }))
    need = sel.need
    return {
        "id": sel.id, "title": sel.title, "vacancy_id": sel.vacancy_id, "created_at": sel.created_at,
        "need": need | {"specialization_name": SPEC_NAMES.get(need["specialization"]),
                        "grade_names": [GRADE_NAMES[g] for g in need["grades"]],
                        "must_skill_names": [SKILL_BY_ID[s].name for s in need["must_skills"] if s in SKILL_BY_ID],
                        "nice_skill_names": [SKILL_BY_ID[s].name for s in need["nice_skills"] if s in SKILL_BY_ID]},
        "categories": sel.categories, "total_in_selection": len(sel.results), "total": total, "page": page,
        "size": size, "filters": filters, "results": rows,
    }


def _filters(specialization, grades, skills, verified_only, has_fsp, work_format, city, allow_relocation, salary_max,
             min_match) -> dict:
    return {k: v for k, v in {
        "specialization": specialization, "grades": [g for g in (grades or "").split(",") if g in GRADE_CODES],
        "skills": [s for s in (skills or "").split(",") if s], "verified_only": verified_only, "has_fsp": has_fsp,
        "work_format": work_format, "city": city, "allow_relocation": allow_relocation, "salary_max": salary_max,
        "min_match": min_match}.items() if v}


@router.post("/selections", status_code=201, summary="Сформировать подборку по потребности",
             description="Потребность — сохранённая вакансия (vacancy_id) или свободное описание (text), которое "
                         "разбирается NLP. Результат сохраняется: уточнение фильтров не теряет исходную подборку.")
def create_selection(data: NeedIn, comp: EmployerCompany, db: DB):
    need, title, vid, parsed = _need_from_input(db, comp, data)
    m = match(db, need)
    sel = Selection(company_id=comp.id, vacancy_id=vid, title=title, need=need.to_dict() | {"parsed": parsed},
                    categories=m["categories"], results=m["results"])
    db.add(sel)
    db.commit()
    return _selection_view(db, comp, sel, {}, 1, 20)


@router.get("/selections", summary="История подборок")
def list_selections(comp: EmployerCompany, db: DB):
    rows = db.scalars(select(Selection).where(Selection.company_id == comp.id).order_by(Selection.created_at.desc()).limit(50))
    return [{"id": s.id, "title": s.title, "vacancy_id": s.vacancy_id, "created_at": s.created_at,
             "total": len(s.results), "specialization_name": SPEC_NAMES.get(s.need.get("specialization")),
             "grade_names": [GRADE_NAMES[g] for g in s.need.get("grades", [])]} for s in rows]


@router.get("/selections/{sid}", summary="Подборка с уточняющими фильтрами (поверх сохранённого результата)")
def get_selection(sid: int, comp: EmployerCompany, db: DB, specialization: str | None = None, grades: str | None = None,
                  skills: str | None = None, verified_only: bool = False, has_fsp: bool = False,
                  work_format: str | None = None, city: str | None = None, allow_relocation: bool = False,
                  salary_max: int | None = None, min_match: int | None = None, page: int = Query(1, ge=1),
                  size: int = Query(20, le=100)):
    sel = db.get(Selection, sid)
    if not sel or sel.company_id != comp.id:
        raise HTTPException(404, "Подборка не найдена")
    f = _filters(specialization, grades, skills, verified_only, has_fsp, work_format, city, allow_relocation,
                 salary_max, min_match)
    return _selection_view(db, comp, sel, f, page, size)


@router.post("/selections/{sid}/refresh", summary="Пересчитать подборку на текущей базе кандидатов")
def refresh_selection(sid: int, comp: EmployerCompany, db: DB):
    sel = db.get(Selection, sid)
    if not sel or sel.company_id != comp.id:
        raise HTTPException(404, "Подборка не найдена")
    need = Need.from_dict(sel.need)
    m = match(db, need)
    sel.categories, sel.results, sel.created_at = m["categories"], m["results"], utcnow()
    db.commit()
    return _selection_view(db, comp, sel, {}, 1, 20)


# ------------------------------------------------------------------ банк кандидатов

@router.get("/candidates", summary="Поиск по банку кандидатов")
def search_candidates(comp: EmployerCompany, db: DB, specialization: str | None = None, grades: str | None = None,
                      skills: str | None = None, verified_only: bool = False, has_fsp: bool = False,
                      work_format: str | None = None, city: str | None = None, salary_max: int | None = None,
                      q: str | None = None, vacancy_id: int | None = None,
                      sort: str = Query("strength", pattern="^(strength|fresh|salary|match)$"),
                      page: int = Query(1, ge=1), size: int = Query(20, le=100)):
    # единица поиска — резюме с категорией (основное или дополнительное); кандидат в выдаче — один раз
    cands = pool_profiles(db, {specialization} if specialization else None)
    gl = [g for g in (grades or "").split(",") if g in GRADE_CODES]
    if gl:
        cands = [c for c in cands if c.grade in gl]
    if city:
        cands = [c for c in cands if (c.city or "").lower() == city.lower()]
    if salary_max:
        cands = [c for c in cands if not c.desired_salary or c.desired_salary <= salary_max]
    want = set(s for s in (skills or "").split(",") if s)
    if want:
        cands = [c for c in cands if want <= (set(c.verified_skills or []) if verified_only
                                              else set(c.verified_skills or []) | set(c.skills or []))]
    if has_fsp:
        cands = [c for c in cands if c.fsp_profile and c.fsp_profile.get("achievements")]
    if work_format:
        cands = [c for c in cands if not c.work_formats or work_format in c.work_formats]
    if q:
        ql = q.lower()
        cands = [c for c in cands if ql in f"{c.headline or ''} {c.about or ''} {c.city or ''}".lower()
                 or ql in " ".join(SKILL_BY_ID[s].name.lower() for s in c.skills or [] if s in SKILL_BY_ID)]
    scores = {}
    if vacancy_id:
        v = _own_vacancy(db, comp, vacancy_id)
        scores = {(r["candidate_id"], r["resume_id"]): r for r in score_candidates(ix.need_from_vacancy(v), cands)}
        sort = "match" if sort == "strength" else sort

    def sc(c):
        return scores.get((c.id, c.resume_id or 0))

    key = {"strength": lambda c: -(c.strength or 0), "fresh": lambda c: -(c.last_active_at.timestamp()),
           "salary": lambda c: c.desired_salary or 10**9,
           "match": lambda c: -((sc(c) or {}).get("score", c.strength or 0))}[sort]
    cands.sort(key=key)
    seen: set[int] = set()
    cands = [c for c in cands if not (c.id in seen or seen.add(c.id))]  # лучшее резюме кандидата по сортировке
    total = len(cands)
    inv, short = _company_relations(db, comp)
    chunk = cands[(page - 1) * size: page * size]
    rows = [_card(db, comp, c, {"invitation_status": inv.get(c.id), "shortlisted": c.id in short,
                                **({"match": sc(c)["match"], "reasons": sc(c)["reasons"]} if sc(c) else {})})
            for c in chunk]
    return {"total": total, "page": page, "size": size, "results": rows}


def _candidate(db, cid: int) -> CandidateProfile:
    c = db.get(CandidateProfile, cid)
    if not c or not c.consent_publish:
        raise HTTPException(404, "Кандидат не найден или скрыл профиль")
    return c


def _visible_profile(c: CandidateProfile, resume_id: int | None):
    """Резюме кандидата, доступное работодателю: скрытое кандидатом дополнительное резюме не показывается."""
    if not resume_id:
        return c
    res = next((r for r in c.resumes if r.id == resume_id and r.visible), None)
    if res is None:
        raise HTTPException(404, "Резюме не найдено или скрыто кандидатом")
    return ResumeView(c, res)


@router.get("/candidates/{cid}", summary="Карточка кандидата (контакты — только после принятия приглашения/отклика)")
def candidate_card(cid: int, comp: EmployerCompany, db: DB, vacancy_id: int | None = None, resume_id: int = 0):
    """resume_id — какое резюме (категорию) показать; 0 — основное."""
    c = _candidate(db, cid)
    prof = _visible_profile(c, resume_id)
    view = employer_view(db, prof, comp)
    audit(db, comp.owner_user_id, "view_candidate", "candidate", c.id, company_id=comp.id)
    if view["contacts_unlocked"]:
        audit(db, comp.owner_user_id, "view_contacts", "candidate", c.id, company_id=comp.id)
    db.commit()
    if vacancy_id:
        v = _own_vacancy(db, comp, vacancy_id)
        sc = score_candidates(ix.need_from_vacancy(v), [prof])[0] if prof.grade else None
        view["match"] = sc
    invs = db.scalars(select(Invitation).where(Invitation.company_id == comp.id, Invitation.candidate_id == c.id)
                      .order_by(Invitation.created_at.desc()))
    view["invitations"] = [{"id": i.id, "title": i.title, "status": i.status,
                            "status_name": ix.INVITATION_STATUSES[i.status], "created_at": i.created_at} for i in invs]
    view["shortlisted"] = bool(db.scalar(select(ShortlistItem.id).where(ShortlistItem.company_id == comp.id,
                                                                        ShortlistItem.candidate_id == c.id)))
    return view


@router.get("/candidates/{cid}/pdf", summary="Стандартизированный PDF-профиль кандидата",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def candidate_pdf(cid: int, comp: EmployerCompany, db: DB, resume_id: int = 0):
    c = _candidate(db, cid)
    pdf = render_profile_pdf(employer_view(db, _visible_profile(c, resume_id), comp))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="candidate-{c.public_id}.pdf"'})


# ------------------------------------------------------------------ шортлист

@router.get("/shortlist", summary="Избранные кандидаты")
def get_shortlist(comp: EmployerCompany, db: DB):
    items = db.scalars(select(ShortlistItem).where(ShortlistItem.company_id == comp.id)
                       .order_by(ShortlistItem.created_at.desc()))
    inv, _ = _company_relations(db, comp)
    out = []
    for it in items:
        c = db.get(CandidateProfile, it.candidate_id)
        if c:
            res = next((r for r in c.resumes if r.id == it.resume_id and r.visible), None) if it.resume_id else None
            prof = ResumeView(c, res) if res else c  # скрытое или удалённое резюме — показываем основное
            out.append({"id": it.id, "note": it.note, "vacancy_id": it.vacancy_id, "created_at": it.created_at,
                        "candidate": _card(db, comp, prof, {"invitation_status": inv.get(c.id), "shortlisted": True})})
    return out


@router.post("/shortlist", status_code=201, summary="Добавить кандидата в избранное")
def add_shortlist(data: ShortlistIn, comp: EmployerCompany, db: DB):
    _candidate(db, data.candidate_id)
    it = db.scalar(select(ShortlistItem).where(ShortlistItem.company_id == comp.id,
                                               ShortlistItem.candidate_id == data.candidate_id))
    if not it:
        it = ShortlistItem(company_id=comp.id, candidate_id=data.candidate_id, vacancy_id=data.vacancy_id, note=data.note)
        db.add(it)
    it.resume_id = data.resume_id or None  # запоминаем резюме, с которым кандидата отметили последним
    db.commit()
    return {"id": it.id, "resume_id": it.resume_id or 0}


@router.delete("/shortlist/{candidate_id}", summary="Убрать из избранного", response_model=Message)
def remove_shortlist(candidate_id: int, comp: EmployerCompany, db: DB):
    db.query(ShortlistItem).filter(ShortlistItem.company_id == comp.id,
                                   ShortlistItem.candidate_id == candidate_id).delete()
    db.commit()
    return Message(detail="ok")


# ------------------------------------------------------------------ приглашения

def _invitation_out(db, comp, i: Invitation) -> dict:
    return {"id": i.id, "status": i.status, "status_name": ix.INVITATION_STATUSES[i.status], "title": i.title,
            "message": i.message, "salary_from": i.salary_from, "salary_to": i.salary_to, "work_format": i.work_format,
            "contact_method": i.contact_method, "vacancy": ix.vacancy_brief(i.vacancy),
            "decline_reason": i.decline_reason, "decline_comment": i.decline_comment,
            "match": round(i.match_score * 100) if i.match_score else None,
            "created_at": i.created_at, "viewed_at": i.viewed_at, "responded_at": i.responded_at,
            "expires_at": i.expires_at, "candidate": _card(db, comp, ix.invitation_profile(i))}


@router.post("/invitations", status_code=201, summary="Пригласить кандидата (вилка ЗП обязательна)",
             responses={409: {"model": Message}, 429: {"model": Message}})
def invite(data: InvitationIn, comp: EmployerCompany, db: DB):
    base = _candidate(db, data.candidate_id)
    cand = _visible_profile(base, data.resume_id)  # приглашение — по конкретному резюме (категории)
    if not cand.grade or not visible(base):
        raise HTTPException(409, "Кандидат не участвует в подборе")
    if not cand.open_to_offers:
        raise HTTPException(409, "Кандидат сейчас не рассматривает предложения")
    pending = db.scalar(select(Invitation).where(Invitation.company_id == comp.id, Invitation.candidate_id == cand.id,
                                                 Invitation.status.in_(["sent", "viewed"])))
    if pending:
        raise HTTPException(409, "У кандидата уже есть ваше активное приглашение")
    day = db.scalar(select(func.count()).select_from(Invitation).where(
        Invitation.company_id == comp.id, Invitation.created_at >= utcnow() - timedelta(days=1))) or 0
    if day >= settings.invitations_per_day_limit:
        raise HTTPException(429, "Достигнут суточный лимит приглашений — это защищает кандидатов от массовых рассылок")
    pv = privacy(cand)
    if pv.get("hide_invites_below_salary") and cand.desired_salary and data.salary_to < cand.desired_salary:
        raise HTTPException(409, "Вилка ниже ожиданий кандидата — он не принимает такие предложения")
    v = _own_vacancy(db, comp, data.vacancy_id) if data.vacancy_id else None
    need = ix.need_from_vacancy(v) if v else Need(
        specialization=cand.grade_specialization, grades=[cand.grade], must_skills=[], nice_skills=[],
        salary_from=data.salary_from, salary_to=data.salary_to, work_format=data.work_format, text=data.message,
        title=data.title)
    need.salary_from, need.salary_to = data.salary_from, data.salary_to
    sc = score_candidates(need, [cand])[0]
    inv = Invitation(company_id=comp.id, candidate_id=cand.id, resume_id=cand.resume_id, vacancy_id=v.id if v else None,
                     title=data.title,
                     message=data.message, salary_from=data.salary_from, salary_to=data.salary_to,
                     work_format=data.work_format or (v.work_format if v else None), contact_method=data.contact_method,
                     match_score=sc["score"], match_snapshot={"reasons": sc["reasons"], "components": sc["components"]},
                     expires_at=utcnow() + timedelta(days=settings.invitation_ttl_days))
    db.add(inv)
    notify(db, cand.user_id, "invitation_new", f"Приглашение от {comp.name}",
           f"«{data.title}», {data.salary_from:,}–{data.salary_to:,} ₽".replace(",", " "), "/candidate/invitations",
           email=True)
    db.commit()
    return _invitation_out(db, comp, inv)


@router.get("/invitations", summary="Отправленные приглашения и их статусы")
def list_invitations(comp: EmployerCompany, db: DB, status: str | None = None):
    invs = list(db.scalars(select(Invitation).where(Invitation.company_id == comp.id).order_by(Invitation.created_at.desc())))
    ix.expire_invitations(db, invs)
    if status:
        invs = [i for i in invs if i.status == status]
    return [_invitation_out(db, comp, i) for i in invs]


@router.post("/invitations/{inv_id}/withdraw", summary="Отозвать приглашение")
def withdraw(inv_id: int, comp: EmployerCompany, db: DB):
    inv = db.get(Invitation, inv_id)
    if not inv or inv.company_id != comp.id:
        raise HTTPException(404, "Приглашение не найдено")
    if inv.status in ("sent", "viewed"):
        inv.status = "withdrawn"
        notify(db, inv.candidate.user_id, "invitation_withdrawn", f"{comp.name} отозвал приглашение «{inv.title}»")
        db.commit()
    return _invitation_out(db, comp, inv)


@router.get("/likelihood/{cid}", summary="Оценка вероятности принятия приглашения при заданной вилке")
def likelihood(cid: int, comp: EmployerCompany, db: DB, salary_to: int, work_format: str | None = None,
               city: str | None = None, resume_id: int = 0):
    c = _visible_profile(_candidate(db, cid), resume_id)
    need = Need(specialization=c.grade_specialization or "backend", grades=[c.grade or "middle"], must_skills=[],
                nice_skills=[], salary_to=salary_to, work_format=work_format, city=city)
    out = response_likelihood(need, c)
    out["salary_fits"] = None if not c.desired_salary else c.desired_salary <= salary_to
    return out


# ------------------------------------------------------------------ регулярные задания

def _task_out(db, t: Task) -> dict:
    counts = {s: db.scalar(select(func.count()).select_from(TaskAssignment).where(
        TaskAssignment.task_id == t.id, TaskAssignment.status == s)) or 0 for s in ("offered", "submitted", "reviewed")}
    return {"id": t.id, "title": t.title, "description": t.description, "specialization": t.specialization,
            "specialization_name": SPEC_NAMES.get(t.specialization), "grades": t.grades, "kind": t.kind,
            "expected_answer": t.expected_answer, "skills": t.skills, "time_estimate_min": t.time_estimate_min,
            "is_active": t.is_active, "vacancy_id": t.vacancy_id, "created_at": t.created_at, "counts": counts,
            **code_tasks.task_payload(t, for_owner=True)}


def _task_fields(data: TaskIn) -> dict:
    """Поля задачи; для задачи с кодом эталон обязан пройти все тесты — иначе ошибка в тестах."""
    if data.specialization not in SPEC_BY_CODE:
        raise HTTPException(422, "Неизвестная специализация")
    fields = data.model_dump()
    fields["tests"] = [t.model_dump() for t in data.tests]
    if data.kind != "code":
        return fields | {"code_language": None, "entrypoint": None, "starter_code": None, "tests": [],
                         "time_limit_ms": None, "compare": None, "reference_solution": None}
    fields["time_limit_ms"] = data.time_limit_ms or 2000
    fields["compare"] = data.compare or "exact"
    if data.reference_solution:
        res = code_tasks.check_reference(CodeTaskSpec(**{k: fields[k] for k in CodeTaskSpec.model_fields}))
        if res["status"] != "ok" or res["passed"] != res["total"]:
            bad = next((x for x in res["tests"] if not x["passed"]), None)
            detail = res.get("error") or (f"тест №{bad['index'] + 1}: ожидалось {bad['expected']!r}, получено "
                                          f"{bad['actual']!r}" + (f" ({bad['error']})" if bad.get("error") else "")
                                          if bad else "")
            raise HTTPException(422, f"Эталонное решение не проходит тесты: {detail}")
    return fields


@router.post("/tasks/check-code", summary="Проверить тесты задачи с кодом эталонным решением (без сохранения)",
             responses={503: {"model": Message}})
def check_code(data: CodeTaskSpec, comp: EmployerCompany):
    """Эталон прогоняется в песочнице на всех тестах: так работодатель находит ошибки в ожидаемых ответах."""
    if not data.reference_solution:
        raise HTTPException(422, "Добавьте эталонное решение")
    return code_tasks.check_reference(data)


@router.get("/tasks", summary="Мои регулярные задания")
def list_tasks(comp: EmployerCompany, db: DB):
    return [_task_out(db, t) for t in db.scalars(select(Task).where(Task.company_id == comp.id)
                                                 .order_by(Task.created_at.desc()))]


@router.post("/tasks", status_code=201, summary="Создать короткое задание для кандидатов категории")
def create_task(data: TaskIn, comp: EmployerCompany, db: DB):
    t = Task(company_id=comp.id, **_task_fields(data))
    db.add(t)
    db.commit()
    return _task_out(db, t)


@router.put("/tasks/{tid}", summary="Изменить задание")
def update_task(tid: int, data: TaskIn, comp: EmployerCompany, db: DB):
    t = db.get(Task, tid)
    if not t or t.company_id != comp.id:
        raise HTTPException(404, "Задание не найдено")
    for k, v in _task_fields(data).items():
        setattr(t, k, v)
    db.commit()
    return _task_out(db, t)


@router.get("/tasks/submissions", summary="Решения кандидатов на проверку")
def submissions(comp: EmployerCompany, db: DB, status: str = "submitted"):
    rows = db.scalars(select(TaskAssignment).join(Task).where(Task.company_id == comp.id, TaskAssignment.status == status)
                      .order_by(TaskAssignment.submitted_at.desc()))
    return [ix.task_view(ta, for_employer=True) for ta in rows]


@router.post("/submissions/{ta_id}/review", summary="Оценить решение (влияет на актуальность профиля кандидата)")
def review(ta_id: int, data: TaskReviewIn, comp: EmployerCompany, db: DB):
    ta = db.get(TaskAssignment, ta_id)
    if not ta or ta.task.company_id != comp.id:
        raise HTTPException(404, "Решение не найдено")
    if ta.status not in ("submitted", "reviewed"):
        raise HTTPException(409, "Решение ещё не отправлено")
    ta.score, ta.feedback, ta.status, ta.reviewed_at = data.score, data.feedback, "reviewed", utcnow()
    ix.apply_task_review(db, ta)
    notify(db, ta.candidate.user_id, "task_reviewed", f"{comp.name} оценил ваше решение: {data.score}/5",
           data.feedback, "/candidate/tasks")
    db.commit()
    return ix.task_view(ta, for_employer=True)


@router.get("/candidates/{cid}/fsp", summary="Достижения ФСП кандидата (если он разрешил показ)")
def candidate_fsp(cid: int, comp: EmployerCompany, db: DB):
    c = _candidate(db, cid)
    if not privacy(c)["show_fsp"]:
        raise HTTPException(403, "Кандидат скрыл достижения ФСП")
    return fsp_summary(c.fsp_profile, c.grade_specialization)


@router.get("/views", summary="Кого из кандидатов просматривали (аудит)")
def views(comp: EmployerCompany, db: DB):
    rows = db.scalars(select(AuditLog).where(AuditLog.user_id == comp.owner_user_id, AuditLog.action == "view_contacts")
                      .order_by(AuditLog.created_at.desc()).limit(100))
    return [{"candidate_id": r.entity_id, "at": r.created_at} for r in rows]
