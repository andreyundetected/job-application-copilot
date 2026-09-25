import datetime

from sqlalchemy.orm import Session

from core.db.models import JobPosting


def create_job_posting(
    session: Session,
    raw_text: str,
    company: str | None = None,
    title: str | None = None,
    source_url: str | None = None,
    source: str = "manual",
    discovery_key: str | None = None,
) -> JobPosting:
    job = JobPosting(
        raw_text=raw_text,
        company=company,
        title=title,
        source_url=source_url,
        source=source,
        discovery_key=discovery_key,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job_posting_by_discovery_key(session: Session, discovery_key: str) -> JobPosting | None:
    return session.query(JobPosting).filter(JobPosting.discovery_key == discovery_key).first()


def update_job_pipeline_stage(
    session: Session, job_posting_id: int, pipeline_stage: str
) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.pipeline_stage = pipeline_stage
    session.commit()
    session.refresh(job)
    return job


def update_job_quick_meta(
    session: Session,
    job_posting_id: int,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    location_country: str | None = None,
    location_state: str | None = None,
    location_city: str | None = None,
    work_mode: str | None = None,
    employment_type: str | None = None,
    tags: list | None = None,
) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    if company is not None:
        job.company = company
    if title is not None:
        job.title = title
    if location is not None:
        job.location = location
    if location_country is not None:
        job.location_country = location_country
    if location_state is not None:
        job.location_state = location_state
    if location_city is not None:
        job.location_city = location_city
    if work_mode is not None:
        job.work_mode = work_mode
    if employment_type is not None:
        job.employment_type = employment_type
    if tags is not None:
        job.tags = tags
    session.commit()
    session.refresh(job)
    return job


def set_job_pending_task(session: Session, job_posting_id: int, task_id: int | None) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.pending_task_id = task_id
    session.commit()
    session.refresh(job)
    return job


def set_job_activity(session: Session, job_posting_id: int, activity_label: str | None) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.activity_label = activity_label
    job.activity_started_at = datetime.datetime.utcnow() if activity_label is not None else None
    session.commit()
    session.refresh(job)
    return job


def increment_job_retry_count(session: Session, job_posting_id: int) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.retry_count = (job.retry_count or 0) + 1
    session.commit()
    session.refresh(job)
    return job


def reset_job_retry_count(session: Session, job_posting_id: int) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.retry_count = 0
    session.commit()
    session.refresh(job)
    return job


def list_stuck_jobs(session: Session, cutoff: datetime.datetime) -> list[tuple[int, str | None, str | None, int]]:
    rows = (
        session.query(JobPosting)
        .filter(
            JobPosting.activity_label.isnot(None),
            JobPosting.activity_started_at.isnot(None),
            JobPosting.activity_started_at <= cutoff,
        )
        .all()
    )
    return [(job.id, job.company, job.title, job.retry_count or 0) for job in rows]


def get_job_posting(session: Session, job_posting_id: int) -> JobPosting | None:
    return session.get(JobPosting, job_posting_id)


def list_job_postings(session: Session, include_archived: bool = True) -> list[JobPosting]:
    query = session.query(JobPosting)
    if not include_archived:
        query = query.filter(JobPosting.archived.is_(False))
    return query.order_by(JobPosting.created_at.desc()).all()


def archive_job_posting(session: Session, job_posting_id: int) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.archived = True
    session.commit()
    session.refresh(job)
    return job


def unarchive_job_posting(session: Session, job_posting_id: int) -> JobPosting | None:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return None
    job.archived = False
    session.commit()
    session.refresh(job)
    return job


def delete_job_posting(session: Session, job_posting_id: int) -> bool:
    from core.db.models import (
        Application,
        ApplicationChatMessage,
        Evaluation,
        FormQuestion,
        GapItem,
        QuestionChange,
        TailoredResume,
        TailoringChange,
        TailoringMessage,
        TailoringSession,
    )

    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return False

    evaluation_ids = [
        row[0]
        for row in session.query(Evaluation.id).filter(Evaluation.job_posting_id == job_posting_id).all()
    ]
    if evaluation_ids:
        session.query(TailoredResume).filter(TailoredResume.evaluation_id.in_(evaluation_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringChange).filter(TailoringChange.evaluation_id.in_(evaluation_ids)).update(
            {TailoringChange.evaluation_id: None}, synchronize_session=False
        )

    tailoring_session_ids = [
        row[0]
        for row in session.query(TailoringSession.id)
        .filter(TailoringSession.job_posting_id == job_posting_id)
        .all()
    ]
    if tailoring_session_ids:
        session.query(GapItem).filter(GapItem.session_id.in_(tailoring_session_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringChange).filter(TailoringChange.session_id.in_(tailoring_session_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringMessage).filter(TailoringMessage.session_id.in_(tailoring_session_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringSession).filter(TailoringSession.id.in_(tailoring_session_ids)).delete(
            synchronize_session=False
        )

    application_ids = [
        row[0]
        for row in session.query(Application.id).filter(Application.job_posting_id == job_posting_id).all()
    ]
    if application_ids:
        form_question_ids = [
            row[0]
            for row in session.query(FormQuestion.id)
            .filter(FormQuestion.application_id.in_(application_ids))
            .all()
        ]
        if form_question_ids:
            session.query(QuestionChange).filter(QuestionChange.question_id.in_(form_question_ids)).delete(
                synchronize_session=False
            )
        session.query(ApplicationChatMessage).filter(
            ApplicationChatMessage.application_id.in_(application_ids)
        ).delete(synchronize_session=False)
        session.query(FormQuestion).filter(FormQuestion.application_id.in_(application_ids)).delete(
            synchronize_session=False
        )
        session.query(Application).filter(Application.id.in_(application_ids)).delete(synchronize_session=False)

    session.query(Evaluation).filter(Evaluation.job_posting_id == job_posting_id).delete(synchronize_session=False)
    session.query(JobPosting).filter(JobPosting.id == job_posting_id).delete(synchronize_session=False)
    session.commit()
    return True