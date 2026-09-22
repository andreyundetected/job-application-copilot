import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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
    content_html: Mapped[str] = mapped_column(Text, nullable=True)
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
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    github_url: Mapped[str] = mapped_column(String(512), nullable=True)
    linkedin_url: Mapped[str] = mapped_column(String(512), nullable=True)
    extra_links: Mapped[list] = mapped_column(JSON, nullable=True)
    extra_info: Mapped[str] = mapped_column(Text, nullable=True)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pregenerate_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pregenerate_min_score: Mapped[int] = mapped_column(Integer, default=7)
    auto_answer_questions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    manual_assist_min_score: Mapped[int] = mapped_column(Integer, default=7)
    preferred_currency: Mapped[str] = mapped_column(String(8), default="USD")
    preferred_salary_period: Mapped[str] = mapped_column(String(8), default="year")


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
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    work_mode: Mapped[str] = mapped_column(String(32), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(64), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=True)
    pending_task_id: Mapped[int] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    pipeline_stage: Mapped[str] = mapped_column(String(32), nullable=True)
    activity_label: Mapped[str] = mapped_column(String(255), nullable=True)

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
    board_order: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    interview_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    interview_notes: Mapped[str] = mapped_column(Text, nullable=True)
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


class TailoringSession(Base):
    __tablename__ = "tailoring_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"))
    resume_version_id: Mapped[int] = mapped_column(ForeignKey("resume_versions.id"))

    working_content: Mapped[dict] = mapped_column(JSON)
    working_html: Mapped[str] = mapped_column(Text, nullable=True)
    style: Mapped[dict] = mapped_column(JSON, nullable=True)
    extracted_keywords: Mapped[list] = mapped_column(JSON, nullable=True)

    messages: Mapped[list["TailoringMessage"]] = relationship(back_populates="session")
    changes: Mapped[list["TailoringChange"]] = relationship(back_populates="session")


class TailoringMessage(Base):
    __tablename__ = "tailoring_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    session_id: Mapped[int] = mapped_column(ForeignKey("tailoring_sessions.id"))

    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)

    session: Mapped["TailoringSession"] = relationship(back_populates="messages")
    changes: Mapped[list["TailoringChange"]] = relationship(back_populates="message")


class TailoringPermission(Base):
    __tablename__ = "tailoring_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16))
    change_type: Mapped[str] = mapped_column(String(64))
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)


class TailoringChange(Base):
    __tablename__ = "tailoring_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"), nullable=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("tailoring_sessions.id"), nullable=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("tailoring_messages.id"), nullable=True)

    level: Mapped[str] = mapped_column(String(16))
    change_type: Mapped[str] = mapped_column(String(64))
    field_path: Mapped[str] = mapped_column(String(255), nullable=True)
    target_ref: Mapped[str] = mapped_column(String(255), nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=True)
    proposed_text: Mapped[str] = mapped_column(Text)
    proposed_content: Mapped[list] = mapped_column(JSON, nullable=True)
    final_text: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    order: Mapped[int] = mapped_column(Integer, default=0)

    evaluation: Mapped["Evaluation"] = relationship()
    session: Mapped["TailoringSession"] = relationship(back_populates="changes")
    message: Mapped["TailoringMessage"] = relationship(back_populates="changes")


class FormQuestion(Base):
    __tablename__ = "form_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    order: Mapped[int] = mapped_column(Integer, default=0)

    question_text: Mapped[str] = mapped_column(Text)
    answer_type: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32), nullable=True)
    options: Mapped[list] = mapped_column(JSON, nullable=True)
    selected_option: Mapped[str] = mapped_column(String(255), nullable=True)
    char_limit: Mapped[int] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=True)
    answer_file_path: Mapped[str] = mapped_column(String(1024), nullable=True)
    needs_manual_input: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str] = mapped_column(Text, nullable=True)
    pending_task_id: Mapped[int] = mapped_column(Integer, nullable=True)
    template_label: Mapped[str] = mapped_column(String(128), nullable=True)
    template_instructions: Mapped[str] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="form_questions")
    changes: Mapped[list["QuestionChange"]] = relationship(back_populates="question")





class ApplicationChatMessage(Base):
    __tablename__ = "application_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    referenced_question_id: Mapped[int] = mapped_column(
        ForeignKey("form_questions.id"), nullable=True
    )

    changes: Mapped[list["QuestionChange"]] = relationship(back_populates="chat_message")


class QuestionChange(Base):
    __tablename__ = "question_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    resolved_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("form_questions.id"))
    chat_message_id: Mapped[int] = mapped_column(
        ForeignKey("application_chat_messages.id"), nullable=True
    )

    original_text: Mapped[str] = mapped_column(Text, nullable=True)
    proposed_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")

    question: Mapped["FormQuestion"] = relationship(back_populates="changes")
    chat_message: Mapped["ApplicationChatMessage"] = relationship(back_populates="changes")


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    queries_planned: Mapped[list] = mapped_column(JSON, nullable=True)
    max_results_override: Mapped[int] = mapped_column(Integer, nullable=True)
    max_queries_override: Mapped[int] = mapped_column(Integer, nullable=True)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    quick_filtered_count: Mapped[int] = mapped_column(Integer, default=0)
    scraped_count: Mapped[int] = mapped_column(Integer, default=0)
    evaluated_count: Mapped[int] = mapped_column(Integer, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    archived_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=True)

    search_results: Mapped[list["SearchResult"]] = relationship(
        back_populates="automation_run"
    )


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    automation_run_id: Mapped[int] = mapped_column(ForeignKey("automation_runs.id"))
    query_text: Mapped[str] = mapped_column(Text)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024))
    url_normalized: Mapped[str] = mapped_column(String(1024), unique=True)
    quick_filter_verdict: Mapped[str] = mapped_column(String(16), nullable=True)
    promoted_job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id"), nullable=True
    )

    automation_run: Mapped["AutomationRun"] = relationship(
        back_populates="search_results"
    )


class AutomationSettings(Base):
    __tablename__ = "automation_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    min_score_to_proceed: Mapped[int] = mapped_column(Integer, default=6)
    max_score_to_archive: Mapped[int] = mapped_column(Integer, default=3)
    quick_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_archive_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    serpent_num_per_query: Mapped[int] = mapped_column(Integer, default=100)
    default_time_range: Mapped[str] = mapped_column(String(8), default="w1")
    saved_queries: Mapped[list] = mapped_column(JSON, nullable=True)
    serpent_cost_per_request: Mapped[float] = mapped_column(Float, nullable=True)


class ManualAssistTailoringPermission(Base):
    __tablename__ = "manual_assist_tailoring_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16))
    change_type: Mapped[str] = mapped_column(String(64))
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)


class ManualAssistBaseQuestion(Base):
    """Same shape as AutomationBaseQuestion, but a fully separate store - the
    manual (Evaluator sidebar) auto-apply/auto-answer config is intentionally
    independent from the Automation page's config, so toggling one never
    affects the other."""

    __tablename__ = "manual_assist_base_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    question_text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)


class QuestionTemplate(Base):
    __tablename__ = "question_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    label: Mapped[str] = mapped_column(String(128))
    trigger_phrases: Mapped[list] = mapped_column(JSON)
    instructions: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)


class AutomationBaseQuestion(Base):
    """A flat, always-asked question for automated applications - no trigger
    matching, since automation never has real pasted application-form text to
    match against (only the job posting text). Every configured row here gets
    an answer generated for every application automation creates."""

    __tablename__ = "automation_base_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    question_text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    provider: Mapped[str] = mapped_column(String(32))
    operation: Mapped[str] = mapped_column(String(32))
    automation_run_id: Mapped[int] = mapped_column(
        ForeignKey("automation_runs.id"), nullable=True
    )
    search_result_id: Mapped[int] = mapped_column(
        ForeignKey("search_results.id"), nullable=True
    )
    job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id"), nullable=True
    )
    requested_num: Mapped[int] = mapped_column(Integer, nullable=True)
    returned_count: Mapped[int] = mapped_column(Integer, nullable=True)
    model: Mapped[str] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=True)
    raw_usage: Mapped[dict] = mapped_column(JSON, nullable=True)