from sqlalchemy.orm import Session

from core.db.models import ResumeVersion


def create_resume_version(
    session: Session, source_type: str, raw_text: str, label: str | None = None
) -> ResumeVersion:
    resume = ResumeVersion(source_type=source_type, raw_text=raw_text, label=label)
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