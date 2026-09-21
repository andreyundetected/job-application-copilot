import datetime

from sqlalchemy.orm import Session

from core.db.models import Application


def create_application(
    session: Session,
    job_posting_id: int,
    tailored_resume_id: int | None = None,
    status: str = "draft",
    source_platform: str | None = None,
    notes: str | None = None,
) -> Application:
    application = Application(
        job_posting_id=job_posting_id,
        tailored_resume_id=tailored_resume_id,
        status=status,
        source_platform=source_platform,
        notes=notes,
    )
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


def ensure_draft_application(
    session: Session, job_posting_id: int, source_platform: str | None = None
) -> Application:
    existing = (
        session.query(Application)
        .filter(Application.job_posting_id == job_posting_id)
        .order_by(Application.created_at.asc())
        .first()
    )
    if existing is not None:
        return existing
    return create_application(session, job_posting_id=job_posting_id, source_platform=source_platform)


def reorder_applications(session: Session, status: str, ordered_ids: list[int]) -> None:
    for index, application_id in enumerate(ordered_ids):
        session.query(Application).filter(
            Application.id == application_id, Application.status == status
        ).update({Application.board_order: index}, synchronize_session=False)
    session.commit()


def get_application(session: Session, application_id: int) -> Application | None:
    return session.get(Application, application_id)


def list_applications(session: Session, status: str | None = None) -> list[Application]:
    query = session.query(Application)
    if status is not None:
        query = query.filter(Application.status == status)
    return query.order_by(Application.created_at.desc()).all()


def update_application_status(
    session: Session,
    application_id: int,
    status: str,
    mark_applied_now: bool = False,
) -> Application | None:
    application = session.get(Application, application_id)
    if application is None:
        return None
    application.status = status
    if mark_applied_now:
        application.applied_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(application)
    return application


def update_application_notes(
    session: Session, application_id: int, notes: str
) -> Application | None:
    application = session.get(Application, application_id)
    if application is None:
        return None
    application.notes = notes
    session.commit()
    session.refresh(application)
    return application


def move_application_status(
    session: Session, application_id: int, status: str
) -> Application | None:
    application = session.get(Application, application_id)
    if application is None:
        return None
    application.status = status
    if status == "applied" and application.applied_at is None:
        application.applied_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(application)
    return application


def update_application_interview(
    session: Session,
    application_id: int,
    interview_at: datetime.datetime | None,
    interview_notes: str | None = None,
) -> Application | None:
    application = session.get(Application, application_id)
    if application is None:
        return None
    application.interview_at = interview_at
    if interview_notes is not None:
        application.interview_notes = interview_notes
    session.commit()
    session.refresh(application)
    return application


def delete_application(session: Session, application_id: int) -> bool:
    application = session.get(Application, application_id)
    if application is None:
        return False
    session.delete(application)
    session.commit()
    return True