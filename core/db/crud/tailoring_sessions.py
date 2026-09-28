from sqlalchemy.orm import Session

from core.db.models import TailoringSession


def create_tailoring_session(
    session: Session,
    job_posting_id: int,
    resume_version_id: int,
    working_content: dict,
    working_html: str | None = None,
    style: dict | None = None,
) -> TailoringSession:
    tailoring_session = TailoringSession(
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        working_content=working_content,
        working_html=working_html,
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


def update_working_html(
    session: Session, tailoring_session_id: int, working_html: str
) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.working_html = working_html
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session


def update_extracted_keywords(
    session: Session, tailoring_session_id: int, extracted_keywords: list
) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.extracted_keywords = extracted_keywords
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session


def mark_block_edited(
    session: Session,
    tailoring_session_id: int,
    field_path: str,
    original_html: str,
    title_suggestion: dict | None = None,
) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    current = dict(tailoring_session.edited_blocks or {})
    existing = current.get(field_path)
    if existing is None:
        record = {"original_html": original_html, "title_suggestions": []}
    elif isinstance(existing, dict):
        record = dict(existing)
    else:
        record = {"original_html": existing, "title_suggestions": []}
    suggestions = list(record.get("title_suggestions") or [])
    if title_suggestion is not None:
        suggestions.append(title_suggestion)
    record["title_suggestions"] = suggestions
    current[field_path] = record
    tailoring_session.edited_blocks = current
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session


def unmark_block_edited(session: Session, tailoring_session_id: int, field_path: str) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    current = dict(tailoring_session.edited_blocks or {})
    if field_path in current:
        del current[field_path]
        tailoring_session.edited_blocks = current
        session.commit()
        session.refresh(tailoring_session)
    return tailoring_session


def save_title_suggestions(
    session: Session, tailoring_session_id: int, suggestions: list
) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.title_suggestions = suggestions
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session