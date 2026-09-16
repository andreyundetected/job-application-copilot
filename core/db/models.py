import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    source_type: Mapped[str] = mapped_column(String(32))
    raw_text: Mapped[str] = mapped_column(Text)
    structured_content: Mapped[dict] = mapped_column(JSON, nullable=True)
    label: Mapped[str] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="resume_version"
    )


class TaskStatus(Base):
    __tablename__ = "task_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    task_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)


class CandidateProfile(Base):
    __tablename__ = "candidate_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    github_url: Mapped[str] = mapped_column(String(512), nullable=True)
    linkedin_url: Mapped[str] = mapped_column(String(512), nullable=True)
    extra_links: Mapped[list] = mapped_column(JSON, nullable=True)
    extra_info: Mapped[str] = mapped_column(Text, nullable=True)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    raw_text: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=True)

    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="job_posting"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job_posting"
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"))
    resume_version_id: Mapped[int] = mapped_column(ForeignKey("resume_versions.id"))

    verdict: Mapped[bool] = mapped_column(Boolean)
    blocker_bullets: Mapped[dict] = mapped_column(JSON, nullable=True)
    fit_score: Mapped[int] = mapped_column(Integer, nullable=True)
    fit_bullets: Mapped[dict] = mapped_column(JSON, nullable=True)
    checked_keywords: Mapped[dict] = mapped_column(JSON, nullable=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="evaluations")
    resume_version: Mapped["ResumeVersion"] = relationship(
        back_populates="evaluations"
    )
    tailored_resumes: Mapped[list["TailoredResume"]] = relationship(
        back_populates="evaluation"
    )


class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"))

    keywords_used: Mapped[dict] = mapped_column(JSON, nullable=True)
    content: Mapped[list] = mapped_column(JSON)
    docx_path: Mapped[str] = mapped_column(String(1024), nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="tailored_resumes")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="tailored_resume"
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"))
    tailored_resume_id: Mapped[int] = mapped_column(
        ForeignKey("tailored_resumes.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), default="draft")
    applied_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    source_platform: Mapped[str] = mapped_column(String(128), nullable=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="applications")
    tailored_resume: Mapped["TailoredResume"] = relationship(
        back_populates="applications"
    )
    form_questions: Mapped[list["FormQuestion"]] = relationship(
        back_populates="application"
    )


class BlockerRule(Base):
    __tablename__ = "blocker_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)


class ScoringFactor(Base):
    __tablename__ = "scoring_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    text: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(8))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    order: Mapped[int] = mapped_column(Integer, default=0)


class FormQuestion(Base):
    __tablename__ = "form_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))

    question_text: Mapped[str] = mapped_column(Text)
    answer_type: Mapped[str] = mapped_column(String(32))
    answer_text: Mapped[str] = mapped_column(Text, nullable=True)
    answer_file_path: Mapped[str] = mapped_column(String(1024), nullable=True)

    application: Mapped["Application"] = relationship(back_populates="form_questions")