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


class ConsentIn(BaseModel):
    kind: Literal["pd_processing", "profile_publication"]
    granted: bool


class SurveyIn(BaseModel):
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


class AnswerIn(BaseModel):
    response_id: int
    answer: Any = Field(None, description="id варианта, список id, строка или число — в зависимости от типа задания")


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


class DeclineIn(BaseModel):
    reason: Literal["salary", "stack", "format", "company", "not_looking", "other"]
    comment: str | None = Field(None, max_length=2000)


class ComplaintIn(BaseModel):
    reason: Literal["fake", "spam", "salary_mismatch", "rude", "other"]
    comment: str | None = Field(None, max_length=2000)


class ApplyIn(BaseModel):
    cover_letter: str | None = Field(None, max_length=5000)


class ApplicationStatusIn(BaseModel):
    status: Literal["viewed", "accepted", "rejected"]
    comment: str | None = Field(None, max_length=2000)


class ShortlistIn(BaseModel):
    candidate_id: int
    vacancy_id: int | None = None
    note: str | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=10000)
    specialization: str
    grades: list[GradeCode] = []
    kind: Literal["solve", "approach"] = "approach"
    expected_answer: str | None = Field(None, description="Эталон/рубрика для предварительной автооценки")
    skills: list[str] = []
    time_estimate_min: int = Field(30, ge=5, le=480)
    vacancy_id: int | None = None
    is_active: bool = True


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
