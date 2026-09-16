from sqlalchemy.orm import Session

from core.db.models import TailoringSession


def create_tailoring_session(
    session: Session,
    job_posting_id: int,
    resume_version_id: int,
    working_content: dict,
    style: dict | None = None,
) -> TailoringSession:
    tailoring_session = TailoringSession(
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        working_content=working_content,
        style=style or {},
    )
    session.add(tailoring_session)
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session


def get_tailoring_session(session: Session, tailoring_session_id: int) -> TailoringSession | None:
    return session.get(TailoringSession, tailoring_session_id)


def get_tailoring_session_for_job(session: Session, job_posting_id: int) -> TailoringSession | None:
    return (
        session.query(TailoringSession)
        .filter(TailoringSession.job_posting_id == job_posting_id)
        .order_by(TailoringSession.created_at.desc())
        .first()
    )


def update_working_content(
    session: Session, tailoring_session_id: int, working_content: dict
) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.working_content = working_content
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session


def update_style(session: Session, tailoring_session_id: int, style: dict) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.style = style
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session