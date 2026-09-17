from sqlalchemy.orm import Session

from core.db.models import ResumeVersion


def create_resume_version(
    session: Session,
    source_type: str,
    raw_text: str,
    structured_content: dict | None = None,
    content_html: str | None = None,
    label: str | None = None,
    is_active: bool = False,
) -> ResumeVersion:
    if is_active:
        session.query(ResumeVersion).filter(
            ResumeVersion.source_type == source_type
        ).update({ResumeVersion.is_active: False})

    resume = ResumeVersion(
        source_type=source_type,
        raw_text=raw_text,
        structured_content=structured_content,
        content_html=content_html,
        label=label,
        is_active=is_active,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def get_resume_version(session: Session, resume_version_id: int) -> ResumeVersion | None:
    return session.get(ResumeVersion, resume_version_id)


def list_resume_versions(
    session: Session, source_type: str | None = None
) -> list[ResumeVersion]:
    query = session.query(ResumeVersion)
    if source_type is not None:
        query = query.filter(ResumeVersion.source_type == source_type)
    return query.order_by(ResumeVersion.created_at.desc()).all()


def get_latest_resume_version(
    session: Session, source_type: str
) -> ResumeVersion | None:
    return (
        session.query(ResumeVersion)
        .filter(ResumeVersion.source_type == source_type)
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )


def get_active_resume_version(
    session: Session, source_type: str
) -> ResumeVersion | None:
    return (
        session.query(ResumeVersion)
        .filter(ResumeVersion.source_type == source_type, ResumeVersion.is_active.is_(True))
        .first()
    )


def set_active_resume_version(
    session: Session, resume_version_id: int
) -> ResumeVersion | None:
    resume = session.get(ResumeVersion, resume_version_id)
    if resume is None:
        return None

    session.query(ResumeVersion).filter(
        ResumeVersion.source_type == resume.source_type
    ).update({ResumeVersion.is_active: False})

    resume.is_active = True
    session.commit()
    session.refresh(resume)
    return resume