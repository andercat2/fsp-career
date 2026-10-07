"""Опрос и адаптивное тестирование кандидата."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, Candidate
from app.core.db import utcnow
from app.models import GradeHistory, SurveyResponse, TestSession
from app.schemas import AnswerIn, Message, ProctoringEventIn, StartTestIn, SurveyIn
from app.services.reference.taxonomy import (
    GRADE_INDEX,
    GRADE_NAMES,
    GRADES,
    INDUSTRIES,
    LANGUAGES,
    SPEC_BY_CODE,
    SPEC_NAMES,
    SPECIALIZATIONS,
    TEAM_ROLES,
    WORK_FORMATS,
)
from app.services.resumes import get_resume, taken_specializations, target_for
from app.services.nlp.resume_parser import claimed_grade_from
from app.services.testing import service

router = APIRouter(prefix="/testing", tags=["Кандидат: опрос и тестирование"])

EXPERIENCE_OPTIONS = {"none": ("Нет коммерческого опыта", 0.0), "lt1": ("До 1 года", 0.5), "1-2": ("1–2 года", 1.5),
                      "2-5": ("2–5 лет", 3.5), "5+": ("Более 5 лет", 6.0)}
EXPECTED_GRADE = {"none": "intern", "lt1": "intern", "1-2": "junior", "2-5": "middle", "5+": "senior"}


@router.get("/survey", summary="Вопросы опроса по отрасли и специализации")
def survey():
    return {
        "questions": [
            {"id": "industries", "type": "multi", "max": 3,
             "title": "Предметные области, где есть опыт или интерес (необязательно)",
             "options": [{"value": i, "label": i} for i in INDUSTRIES]},
            {"id": "specialization", "type": "single", "title": "ИТ-направление и специализация",
             "options": [{"value": s["code"], "label": s["name"], "hint": s["description"], "group": s["direction"]}
                         for s in SPECIALIZATIONS]},
            {"id": "language", "type": "single", "title": "Основной язык / стек", "depends_on": "specialization",
             "options_by": {s["code"]: [{"value": lang, "label": LANGUAGES[lang]} for lang in s["languages"]]
                            for s in SPECIALIZATIONS}},
            {"id": "experience", "type": "single", "title": "Коммерческий опыт по специализации",
             "options": [{"value": k, "label": v[0]} for k, v in EXPERIENCE_OPTIONS.items()]},
            {"id": "roles", "type": "multi", "title": "Чем вы занимались в команде",
             "options": [{"value": k, "label": v} for k, v in TEAM_ROLES.items()]},
            {"id": "work_formats", "type": "multi", "title": "Предпочтительный формат работы",
             "options": [{"value": k, "label": v} for k, v in WORK_FORMATS.items()]},
            {"id": "claimed_grade", "type": "single", "title": "Ваш предполагаемый грейд",
             "options": [{"value": g["code"], "label": g["name"], "hint": f"{g['experience']}. {g['description']}"}
                         for g in GRADES]},
            {"id": "fsp_participant", "type": "boolean", "title": "Участвовали ли вы в соревнованиях ФСП?"},
        ]
    }


@router.post("/survey", summary="Сохранить ответы опроса", responses={422: {"model": Message}})
def submit_survey(data: SurveyIn, cand: Candidate, db: DB):
    sp = SPEC_BY_CODE.get(data.specialization)
    if not sp:
        raise HTTPException(422, "Неизвестная специализация")
    if data.resume_id:
        res = get_resume(cand, data.resume_id)
        if data.specialization != res.specialization:
            raise HTTPException(409, "Специализация дополнительного резюме фиксирована: для другой специализации "
                                     "создайте новое резюме")
        return save_survey(db, cand, res, data, sp)
    if data.specialization in taken_specializations(cand, except_resume=0):
        raise HTTPException(409, "По этой специализации у вас уже есть дополнительное резюме — пройдите опрос в нём")
    return save_survey(db, cand, cand, data, sp)


def save_survey(db, cand, target, data: SurveyIn, sp: dict) -> dict:
    """target — профиль (основное резюме) или дополнительное резюме: поля опроса у них одинаковые."""
    lang = data.language if data.language in sp["languages"] else sp["languages"][0]
    warnings = []
    expected = EXPECTED_GRADE[data.experience]
    if GRADE_INDEX[data.claimed_grade] - GRADE_INDEX[expected] >= 2:
        warnings.append(f"Вы выбрали {GRADE_NAMES[data.claimed_grade]} при опыте «{EXPERIENCE_OPTIONS[data.experience][0]}». "
                        "Это допустимо — тест покажет реальный уровень, а при неудаче можно пройти тест уровнем ниже.")
    if target.grade and target.grade_specialization and target.grade_specialization != data.specialization:
        warnings.append(f"Текущая категория «{SPEC_NAMES[target.grade_specialization]} · {GRADE_NAMES[target.grade]}» "
                        "сохранится, пока вы не пройдёте тест по новой специализации. Если хотите сохранить обе "
                        "категории — добавьте отдельное резюме под новую специализацию.")
    rid = target.id if target is not cand else None
    db.add(SurveyResponse(candidate_id=cand.id, resume_id=rid, answers=data.model_dump(),
                          specialization=data.specialization, claimed_grade=data.claimed_grade, warnings=warnings))
    target.industries = data.industries
    target.specialization = data.specialization
    target.primary_language = lang
    target.claimed_grade = data.claimed_grade
    cand.roles = list(dict.fromkeys((cand.roles or []) + data.roles))
    if data.work_formats:
        cand.work_formats = data.work_formats
    if cand.experience_years is None:
        cand.experience_years = EXPERIENCE_OPTIONS[data.experience][1]
    target.survey_completed_at = utcnow()
    db.commit()
    return {"warnings": warnings, "eligibility": service.eligibility(db, cand, rid)}


@router.get("/survey/history", summary="История ответов на опрос")
def survey_history(cand: Candidate, db: DB):
    rows = db.scalars(select(SurveyResponse).where(SurveyResponse.candidate_id == cand.id)
                      .order_by(SurveyResponse.created_at.desc()))
    return [{"id": r.id, "resume_id": r.resume_id or 0, "specialization": r.specialization,
             "specialization_name": SPEC_NAMES.get(r.specialization),
             "claimed_grade": r.claimed_grade, "warnings": r.warnings, "answers": r.answers, "created_at": r.created_at}
            for r in rows]


@router.get("/grade-hint", summary="Подсказка грейда по резюме: стаж и должности (выбор грейда — за кандидатом)")
def grade_hint(cand: Candidate, resume_id: int = 0):
    """Постановщики допускают подсказку грейда по резюме; выбирает грейд сам кандидат, тест подтверждает или нет."""
    prof = target_for(cand, resume_id)
    title = (prof.title if resume_id else cand.headline) or ""
    positions = " ".join((e.get("position") or "") for e in (cand.experience or []))
    grade = claimed_grade_from(f"{title} {positions}", cand.experience_years)
    if not grade:
        return {"grade": None, "grade_name": None, "reason": None}
    by_title = claimed_grade_from(f"{title} {positions}", None) == grade
    years = cand.experience_years
    reason = (f"по должности в резюме" if by_title else
              f"по стажу {str(round(years, 1)).replace('.', ',')} г." if years is not None else "по резюме")
    return {"grade": grade, "grade_name": GRADE_NAMES[grade], "reason": reason}


@router.get("/eligibility", summary="Какие уровни теста доступны сейчас (с учётом ограничений по частоте)")
def eligibility(cand: Candidate, db: DB, resume_id: int = 0):
    """resume_id — резюме (категория): 0 — основное. Ограничения частоты действуют для каждой категории отдельно."""
    target_for(cand, resume_id)  # 404, если резюме чужое или удалено
    return service.eligibility(db, cand, resume_id or None)


@router.post("/sessions", summary="Начать тест на выбранный грейд (или продолжить незавершённый)",
             responses={409: {"model": Message}})
def start(data: StartTestIn, cand: Candidate, db: DB):
    sess = service.start_session(db, cand, data.grade, data.resume_id or None)
    return service.question_view(sess, service.current_response(sess))


def _own_session(db, cand, token: str) -> TestSession:
    sess = db.scalar(select(TestSession).where(TestSession.token == token, TestSession.candidate_id == cand.id))
    if not sess:
        raise HTTPException(404, "Сессия не найдена")
    return sess


@router.get("/sessions/{token}", summary="Состояние сессии: текущее задание или результат")
def get_session(token: str, cand: Candidate, db: DB):
    sess = _own_session(db, cand, token)
    return service.question_view(sess, service.current_response(sess) if sess.status == "in_progress" else None)


@router.post("/sessions/{token}/answer", summary="Ответить на текущее задание",
             responses={409: {"model": Message}})
def answer(token: str, data: AnswerIn, cand: Candidate, db: DB):
    sess = _own_session(db, cand, token)
    return service.submit_answer(db, sess, data.response_id, data.answer)


@router.post("/sessions/{token}/proctoring", summary="Событие прокторинга: снимок экрана, печать, копирование, "
             "уход со вкладки", responses={409: {"model": Message}})
def proctoring(token: str, data: ProctoringEventIn, cand: Candidate, db: DB):
    """1-й снимок экрана (печать, копирование текста задания) — предупреждение; 2-й — тест завершается
    досрочно, нарушение фиксируется, оценка уровня понижается. Уход со вкладки только учитывается."""
    sess = _own_session(db, cand, token)
    return service.record_proctoring(db, sess, data.kind, data.method, data.away_ms)


@router.post("/sessions/{token}/accept-suggested", summary="Принять грейд ниже заявленного по этому же тесту",
             responses={409: {"model": Message}})
def accept_suggested(token: str, cand: Candidate, db: DB):
    """Если заявленный грейд не подтверждён, но тест с вероятностью ≥ 0.8 показал уровень не ниже грейда на ступень
    ниже, этот грейд можно принять сразу, без отдельного теста. Повысить грейд по тому же тесту нельзя."""
    return service.accept_suggested(db, _own_session(db, cand, token))


@router.post("/sessions/{token}/abandon", summary="Прервать тест", response_model=Message)
def abandon(token: str, cand: Candidate, db: DB):
    service.abandon(db, _own_session(db, cand, token))
    return Message(detail="Тест прерван. Попытка засчитана для ограничения частоты.")


@router.get("/history", summary="История тестов и смен грейда")
def history(cand: Candidate, db: DB):
    grades = db.scalars(select(GradeHistory).where(GradeHistory.candidate_id == cand.id)
                        .order_by(GradeHistory.created_at.desc()))
    return {
        "sessions": service.history(db, cand),
        "grade_changes": [{"specialization": g.specialization, "specialization_name": SPEC_NAMES.get(g.specialization),
                           "old_grade": g.old_grade, "new_grade": g.new_grade,
                           "new_grade_name": GRADE_NAMES.get(g.new_grade), "theta": g.theta, "created_at": g.created_at}
                          for g in grades],
    }
