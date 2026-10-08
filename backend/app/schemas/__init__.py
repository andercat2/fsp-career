"""Pydantic-схемы запросов и ответов (формируют спецификацию OpenAPI)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["candidate", "employer"]
GradeCode = Literal["intern", "junior", "middle", "senior"]
WorkFormat = Literal["office", "hybrid", "remote"]


class Message(BaseModel):
    detail: str


# ------------------------------------------------------------------ auth

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Не короче 8 символов")
    role: Role
    company_name: str | None = Field(None, description="Для работодателя — название компании")
    consent_pd: bool = Field(description="Согласие на обработку персональных данных (152-ФЗ)")

    @field_validator("consent_pd")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Без согласия на обработку персональных данных регистрация невозможна")
        return v


class RegisterOut(BaseModel):
    detail: str
    email: str
    dev_code: str | None = Field(None, description="Только в dev-режиме: код подтверждения для демонстрации")


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str
    email_verified: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ------------------------------------------------------------------ candidate

class ExperienceItem(BaseModel):
    company: str | None = None
    position: str | None = None
    start: str | None = Field(None, description="ГГГГ-ММ")
    end: str | None = Field(None, description="ГГГГ-ММ или null — по настоящее время")
    description: str | None = None


class EducationItem(BaseModel):
    title: str = Field(max_length=300, description="Учебное заведение или курс")
    year: int | None = Field(None, ge=1950, le=2100, description="Год окончания")
    level: str | None = Field(None, max_length=60, description="Высшее, бакалавр, магистр, курсы…")
    specialty: str | None = Field(None, max_length=300, description="Факультет, специальность")


class LanguageItem(BaseModel):
    name: str = Field(max_length=40)
    level: str | None = Field(None, max_length=80)


class CandidateProfileIn(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=40)
    telegram: str | None = Field(None, max_length=64)
    contact_email: EmailStr | None = None
    city: str | None = Field(None, max_length=120)
    relocation: bool = False
    work_formats: list[WorkFormat] = []
    desired_salary: int | None = Field(None, ge=0, le=10_000_000)
    headline: str | None = Field(None, max_length=255)
    about: str | None = Field(None, max_length=5000)
    experience_years: float | None = Field(None, ge=0, le=60)
    experience: list[ExperienceItem] = []
    education: list[EducationItem] = []
    skills: list[str] = Field([], description="Канонические id навыков из /reference/skills")
    roles: list[str] = []
    soft_skills: list[str] = []
    languages: list[LanguageItem] = []
    links: dict[str, str] = {}
    open_to_offers: bool = True


class PrivacyIn(BaseModel):
    show_name: bool = False
    show_salary: bool = True
    show_companies: bool = True
    show_fsp: bool = True
    visible_in_search: bool = True
    hide_invites_below_salary: bool = False
    show_unconfirmed: bool = Field(True, description="Пока грейд не подтверждён тестом — показываться работодателям "
                                                     "со статусом «не подтверждён» и ниже подтверждённых кандидатов")


class ConsentIn(BaseModel):
    kind: Literal["pd_processing", "profile_publication"]
    granted: bool


class SurveyIn(BaseModel):
    resume_id: int | None = Field(None, ge=0, description="0 / не указан — основное резюме; id — дополнительное")
    industries: list[str] = Field([], max_length=3)
    specialization: str
    language: str | None = None
    experience: Literal["none", "lt1", "1-2", "2-5", "5+"]
    roles: list[str] = []
    work_formats: list[WorkFormat] = []
    claimed_grade: GradeCode
    fsp_participant: bool = False


class StartTestIn(BaseModel):
    grade: GradeCode
    resume_id: int | None = Field(None, ge=0, description="Резюме (категория), по которому идёт тест; 0 — основное")
    mode: Literal["full", "express"] = Field("full", description="full — тест, определяющий категорию (12–24 задания); "
                                                                 "express — пробная оценка уровня за ≈7 минут (8 заданий), "
                                                                 "категорию не присваивает")


class GuestIn(BaseModel):
    specialization: str = Field(description="Специализация (код из справочника)")
    language: str = Field(description="Основной язык / стек (код из справочника)")
    claimed_grade: GradeCode = "junior"
    consent_pd: bool = Field(description="Согласие на обработку данных демо-аккаунта")

    @field_validator("consent_pd")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Нужно согласие на обработку данных")
        return v


class ResumeCreateIn(SurveyIn):
    """Новое резюме под другую специализацию — это опрос по ней (категорию затем определит тест)."""
    title: str | None = Field(None, max_length=255, description="Заголовок резюме, например «ML-инженер (CV)»")
    skills: list[str] | None = Field(None, description="Навыки резюме; не указаны — копируются из профиля")
    desired_salary: int | None = Field(None, ge=0, le=10_000_000)
    about: str | None = Field(None, max_length=5000)


class ResumeIn(BaseModel):
    title: str | None = Field(None, max_length=255)
    skills: list[str] = []
    desired_salary: int | None = Field(None, ge=0, le=10_000_000)
    about: str | None = Field(None, max_length=5000)
    visible: bool = True


class AnswerIn(BaseModel):
    response_id: int
    answer: Any = Field(None, description="id варианта, список id, строка или число — в зависимости от типа задания")


class ProctoringEventIn(BaseModel):
    kind: Literal["screenshot", "print", "copy", "focus_loss"] = Field(
        description="screenshot — снимок экрана (PrintScreen, Win+Shift+S, ⌘⇧3/4/5); print — печать или сохранение "
                    "страницы; copy — копирование текста задания; focus_loss — уход со вкладки (только учитывается)")
    method: str | None = Field(None, max_length=40, description="Как обнаружено: клавиша, сочетание, событие браузера")
    away_ms: int | None = Field(None, ge=0, le=3_600_000, description="Сколько длился уход со вкладки, мс")


# ------------------------------------------------------------------ employer

class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(None, max_length=5000)
    industry: str | None = None
    website: str | None = None
    city: str | None = None
    size: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    contact_telegram: str | None = None
    ats_webhook_url: str | None = Field(None, description="URL ATS-системы для webhook о принятых приглашениях")


class ParseNeedIn(BaseModel):
    title: str = ""
    text: str = Field(min_length=10, max_length=20000)


class SalaryRange(BaseModel):
    salary_from: int = Field(gt=0, description="Нижняя граница, ₽ (обязательно)")
    salary_to: int = Field(gt=0, description="Верхняя граница, ₽ (обязательно)")

    @model_validator(mode="after")
    def _order(self):
        if self.salary_from > self.salary_to:
            raise ValueError("Нижняя граница зарплаты больше верхней")
        return self


class VacancyIn(SalaryRange):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field("", max_length=20000)
    team_description: str | None = Field(None, max_length=5000)
    specialization: str
    grades: list[GradeCode] = Field(min_length=1)
    must_skills: list[str] = []
    nice_skills: list[str] = []
    language: str | None = None
    work_format: WorkFormat = "hybrid"
    city: str | None = None
    employment: Literal["full", "part", "project", "internship"] = "full"
    require_fsp: bool = False
    is_published: bool = False


class NeedIn(BaseModel):
    """Потребность для подбора: ссылка на сохранённую вакансию или произвольное описание."""
    vacancy_id: int | None = None
    title: str | None = None
    text: str | None = None
    specialization: str | None = None
    grades: list[GradeCode] | None = None
    must_skills: list[str] | None = None
    nice_skills: list[str] | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    work_format: WorkFormat | None = None
    city: str | None = None
    require_fsp: bool | None = None


class InvitationIn(SalaryRange):
    candidate_id: int
    vacancy_id: int | None = Field(None, description="Привязка к вакансии необязательна")
    title: str = Field(min_length=3, max_length=255, description="Позиция / суть предложения")
    message: str = Field(min_length=10, max_length=5000, description="Описание предложения")
    work_format: WorkFormat | None = None
    contact_method: str = Field(min_length=3, max_length=255, description="Способ связи (Telegram, e-mail, телефон)")
    selection_id: int | None = None
    resume_id: int | None = Field(None, ge=0, description="По какому резюме (категории) приглашение; 0 — основное")


class DeclineIn(BaseModel):
    reason: Literal["salary", "stack", "format", "company", "not_looking", "other"]
    comment: str | None = Field(None, max_length=2000)


class ComplaintIn(BaseModel):
    reason: Literal["fake", "spam", "salary_mismatch", "rude", "other"]
    comment: str | None = Field(None, max_length=2000)


class ApplyIn(BaseModel):
    cover_letter: str | None = Field(None, max_length=5000)
    resume_id: int | None = Field(None, ge=0, description="Каким резюме откликнуться; не указано — лучшим для вакансии")


class ApplicationStatusIn(BaseModel):
    status: Literal["viewed", "accepted", "rejected"]
    comment: str | None = Field(None, max_length=2000)


class ShortlistIn(BaseModel):
    candidate_id: int
    resume_id: int | None = Field(None, ge=0, description="Резюме (категория), с которым кандидат добавлен; 0 — основное")
    vacancy_id: int | None = None
    note: str | None = None


class CodeTest(BaseModel):
    args: list[Any] = Field(description="Аргументы функции — JSON-массив, например [[1, 2, 3], 2]")
    expected: Any = Field(None, description="Ожидаемый результат (JSON)")
    hidden: bool = Field(False, description="Скрытый тест: кандидат видит только «пройден / не пройден»")
    name: str | None = Field(None, max_length=120)


class CodeTaskSpec(BaseModel):
    code_language: Literal["python", "javascript"] = "python"
    entrypoint: str = Field("solve", pattern=r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$", description="Имя функции")
    tests: list[CodeTest] = Field(default_factory=list, max_length=50)
    time_limit_ms: int = Field(2000, ge=500, le=10000, description="Лимит времени на все тесты прогона")
    compare: Literal["exact", "unordered"] = "exact"
    reference_solution: str | None = Field(None, max_length=20000)


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=10000)
    specialization: str
    grades: list[GradeCode] = []
    kind: Literal["solve", "approach", "code"] = "approach"
    code_language: Literal["python", "javascript"] | None = None
    entrypoint: str | None = Field(None, pattern=r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")
    starter_code: str | None = Field(None, max_length=20000)
    tests: list[CodeTest] = Field(default_factory=list, max_length=50)
    time_limit_ms: int | None = Field(None, ge=500, le=10000)
    compare: Literal["exact", "unordered"] | None = None
    reference_solution: str | None = Field(None, max_length=20000)
    expected_answer: str | None = Field(None, description="Эталон/рубрика для предварительной автооценки")
    skills: list[str] = []
    time_estimate_min: int = Field(30, ge=5, le=480)
    vacancy_id: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _code_task(self):
        if self.kind == "code":
            if not self.code_language or not self.entrypoint:
                raise ValueError("Для задачи с кодом укажите язык и имя функции")
            if not any(not t.hidden for t in self.tests) or not any(t.hidden for t in self.tests):
                raise ValueError("Нужен хотя бы один открытый тест (пример для кандидата) и хотя бы один скрытый")
        return self


class CodeRunIn(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    signals: dict[str, Any] | None = Field(None, description="Вставки из буфера, уходы со вкладки, время решения")


class TaskSubmitIn(BaseModel):
    answer: str = Field(min_length=10, max_length=20000)


class TaskReviewIn(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str | None = Field(None, max_length=5000)


class EvalCandidate(BaseModel):
    id: str
    specialization: str
    grade: GradeCode
    theta: float = Field(description="Оценка способности по тесту")
    skills: list[str] = []
    verified_skills: list[str] = []
    desired_salary: int | None = None
    work_formats: list[WorkFormat] = []
    city: str | None = None
    fsp_achievements: list[dict] = []
    text: str = ""


class EvalRankIn(BaseModel):
    vacancy_text: str
    vacancy_title: str = ""
    candidates: list[EvalCandidate] = Field(max_length=2000)


# ---------------------------------------------------------------- черновики заданий от LLM (админка)

class DraftBatchIn(BaseModel):
    specialization: str = Field(description="Специализация (направление), код из справочника")
    domain: str | None = Field(None, description="Раздел теста; пусто — разделы по долям состава теста")
    level: int = Field(3, ge=1, le=5, description="Уровень сложности 1–5: стажёр … senior")
    count: int = Field(3, ge=1, le=10, description="Сколько черновиков подготовить для проверки")
    topic: str | None = Field(None, max_length=200, description="Тема-подсказка для модели (необязательно)")


class DraftEditIn(BaseModel):
    """Версия эксперта: можно изменить вопрос, код, варианты, правильный ответ и пояснение."""
    topic: str = Field(min_length=2, max_length=200)
    level: int = Field(ge=1, le=5)
    prompt: str = Field(min_length=10, max_length=4000)
    code: str | None = Field(None, max_length=4000)
    code_lang: str | None = Field(None, max_length=20)
    options: list[str] = Field(min_length=4, max_length=4)
    correct: int = Field(ge=0, le=3, description="Индекс правильного варианта")
    explanation: str = Field("", max_length=2000)

    @field_validator("options")
    @classmethod
    def _strip(cls, v: list[str]) -> list[str]:
        return [x.strip() for x in v]


class DraftRejectIn(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
