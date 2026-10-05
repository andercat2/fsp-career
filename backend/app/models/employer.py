from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(40))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_telegram: Mapped[str | None] = mapped_column(String(64))
    # Задел под защиту от недобросовестных работодателей и ATS-интеграцию
    domain_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    ats_webhook_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner = relationship("User", back_populates="company")


class Vacancy(Base):
    """Потребность работодателя. Может быть приватной (только для подбора) или опубликованной вакансией."""

    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    team_description: Mapped[str | None] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    grades: Mapped[list] = mapped_column(JSON, default=list)
    must_skills: Mapped[list] = mapped_column(JSON, default=list)
    nice_skills: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str | None] = mapped_column(String(40))
    work_format: Mapped[str] = mapped_column(String(20), default="hybrid")
    city: Mapped[str | None] = mapped_column(String(120))
    employment: Mapped[str] = mapped_column(String(20), default="full")
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    require_fsp: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | closed
    parsed: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company = relationship("Company")


class Selection(Base):
    """Сохранённая подборка: результат подбора по потребности. Уточнение фильтров работает поверх неё,
    поэтому исходная подборка не теряется."""

    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    need: Mapped[dict] = mapped_column(JSON)  # нормализованная потребность
    categories: Mapped[list] = mapped_column(JSON)
    results: Mapped[list] = mapped_column(JSON)  # [{candidate_id, score, ...}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ShortlistItem(Base):
    __tablename__ = "shortlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    resume_id: Mapped[int | None] = mapped_column(Integer)  # по какому резюме (категории) приглашён; None — основное
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    work_format: Mapped[str | None] = mapped_column(String(20))
    contact_method: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="sent", index=True)
    decline_reason: Mapped[str | None] = mapped_column(String(40))
    decline_comment: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[float | None] = mapped_column(Float)
    match_snapshot: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    company = relationship("Company")
    vacancy = relationship("Vacancy")
    candidate = relationship("CandidateProfile")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int | None] = mapped_column(Integer)  # каким резюме откликнулся; None — основное
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent|viewed|accepted|rejected|withdrawn
    match_score: Mapped[float | None] = mapped_column(Float)
    employer_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    vacancy = relationship("Vacancy")
    candidate = relationship("CandidateProfile")


class Task(Base):
    """Регулярное короткое задание от работодателя: решить или предложить подход."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    grades: Mapped[list] = mapped_column(JSON, default=list)
    kind: Mapped[str] = mapped_column(String(20), default="approach")  # solve | approach
    expected_answer: Mapped[str | None] = mapped_column(Text)  # для автопроверки (опционально)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    time_estimate_min: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company = relationship("Company")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="offered")  # offered|submitted|reviewed|skipped
    answer: Mapped[str | None] = mapped_column(Text)
    auto_score: Mapped[float | None] = mapped_column(Float)
    score: Mapped[int | None] = mapped_column(Integer)  # 1..5 от работодателя
    feedback: Mapped[str | None] = mapped_column(Text)
    offered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    task = relationship("Task")
    candidate = relationship("CandidateProfile")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    invitation_id: Mapped[int | None] = mapped_column(ForeignKey("invitations.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
