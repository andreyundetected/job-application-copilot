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