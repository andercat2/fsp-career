from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow

DEFAULT_PRIVACY = {
    "show_name": False,  # до принятия приглашения работодатель видит анонимный код кандидата
    "show_salary": True,  # показывать ожидания по ЗП
    "show_companies": True,  # показывать названия прошлых работодателей
    "show_fsp": True,  # показывать достижения ФСП
    "visible_in_search": True,  # участвовать в банке кандидатов
    "hide_invites_below_salary": False,  # не принимать приглашения с вилкой ниже ожиданий
    "show_unconfirmed": True,  # пока грейд не подтверждён — показываться работодателям со статусом и ниже в выдаче
}


class CandidateProfile(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)

    # Резюме / анкета
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    telegram: Mapped[str | None] = mapped_column(String(64))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    work_formats: Mapped[list] = mapped_column(JSON, default=list)  # office | hybrid | remote
    desired_salary: Mapped[int | None] = mapped_column(Integer)
    headline: Mapped[str | None] = mapped_column(String(255))
    about: Mapped[str | None] = mapped_column(Text)
    experience_years: Mapped[float | None] = mapped_column(Float)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)  # канонические id навыков (самоописание)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)  # [{name, level}]
    links: Mapped[dict] = mapped_column(JSON, default=dict)
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(String(255))

    # Опрос (заявленные значения)
    industries: Mapped[list] = mapped_column(JSON, default=list)
    specialization: Mapped[str | None] = mapped_column(String(40), index=True)
    primary_language: Mapped[str | None] = mapped_column(String(40))
    claimed_grade: Mapped[str | None] = mapped_column(String(20))
    survey_completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Категория, присвоенная по результатам тестирования (то, что видит работодатель)
    grade: Mapped[str | None] = mapped_column(String(20), index=True)
    grade_specialization: Mapped[str | None] = mapped_column(String(40), index=True)
    grade_theta: Mapped[float | None] = mapped_column(Float)
    grade_se: Mapped[float | None] = mapped_column(Float)
    grade_assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    domain_scores: Mapped[dict] = mapped_column(JSON, default=dict)  # домен -> {score, n, correct}
    verified_skills: Mapped[list] = mapped_column(JSON, default=list)  # навыки, подтверждённые тестом
    # Грейд, заявленный в последнем тесте и не подтверждённый им, пока подтверждённого грейда нет: кандидат остаётся
    # в выдаче со статусом «не подтверждён» и ниже подтверждённых (рекомендация постановщиков); θ — измеренная тестом
    unconfirmed_grade: Mapped[str | None] = mapped_column(String(20))
    unconfirmed_theta: Mapped[float | None] = mapped_column(Float)
    unconfirmed_se: Mapped[float | None] = mapped_column(Float)
    unconfirmed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ФСП
    fsp_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    fsp_linked_at: Mapped[datetime | None] = mapped_column(DateTime)
    fsp_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    fsp_profile: Mapped[dict | None] = mapped_column(JSON)  # кэш данных реестра
    fsp_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1, агрегат достижений

    # Регулярные задания
    tasks_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    tasks_done: Mapped[int] = mapped_column(Integer, default=0)
    last_task_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Приватность и согласия
    privacy: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_PRIVACY))
    consent_pd: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    open_to_offers: Mapped[bool] = mapped_column(Boolean, default=True)

    strength: Mapped[float] = mapped_column(Float, default=0.0)  # сила подтверждённого профиля 0..1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User", back_populates="candidate")
    resumes = relationship("CandidateResume", back_populates="candidate", cascade="all, delete-orphan",
                           order_by="CandidateResume.id")

    # Основное резюме — сам профиль: у него нет отдельного id (в API — 0), заголовок резюме = headline
    resume_id = None

    @property
    def resume_title(self) -> str | None:
        return self.headline


class CandidateResume(Base):
    """Дополнительное резюме кандидата под другую специализацию: свой опрос, свой тест и своя категория
    (специализация × грейд). Общие данные — ФИО, контакты, город, опыт, образование, ФСП — берутся из профиля.
    Поля категории называются так же, как в CandidateProfile: сервисы тестирования и подбора работают с обоими."""
    __tablename__ = "candidate_resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    about: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    desired_salary: Mapped[int | None] = mapped_column(Integer)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(String(255))

    # Опрос
    industries: Mapped[list] = mapped_column(JSON, default=list)
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    primary_language: Mapped[str | None] = mapped_column(String(40))
    claimed_grade: Mapped[str | None] = mapped_column(String(20))
    survey_completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Категория по результатам тестирования
    grade: Mapped[str | None] = mapped_column(String(20), index=True)
    grade_specialization: Mapped[str | None] = mapped_column(String(40), index=True)
    grade_theta: Mapped[float | None] = mapped_column(Float)
    grade_se: Mapped[float | None] = mapped_column(Float)
    grade_assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    domain_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_skills: Mapped[list] = mapped_column(JSON, default=list)
    unconfirmed_grade: Mapped[str | None] = mapped_column(String(20))  # как в CandidateProfile
    unconfirmed_theta: Mapped[float | None] = mapped_column(Float)
    unconfirmed_se: Mapped[float | None] = mapped_column(Float)
    unconfirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    fsp_score: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    candidate = relationship("CandidateProfile", back_populates="resumes")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    resume_id: Mapped[int | None] = mapped_column(Integer)  # None — основное резюме
    specialization: Mapped[str] = mapped_column(String(40))
    claimed_grade: Mapped[str] = mapped_column(String(20))
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GradeHistory(Base):
    __tablename__ = "grade_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int | None] = mapped_column(Integer)  # None — основное резюме
    specialization: Mapped[str] = mapped_column(String(40))
    old_grade: Mapped[str | None] = mapped_column(String(20))
    new_grade: Mapped[str] = mapped_column(String(20))
    theta: Mapped[float | None] = mapped_column(Float)
    session_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
