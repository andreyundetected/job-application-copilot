from sqlalchemy.orm import Session

from core.db.models import ResumeVersion, TailoringSession


def set_resume_blocks(session: Session, resume_version_id: int, blocks: list | None) -> ResumeVersion | None:
    resume = session.get(ResumeVersion, resume_version_id)
    if resume is None:
        return None
    resume.blocks = blocks
    session.commit()
    session.refresh(resume)
    return resume


def set_session_blocks(session: Session, tailoring_session_id: int, blocks: list | None) -> TailoringSession | None:
    tailoring_session = session.get(TailoringSession, tailoring_session_id)
    if tailoring_session is None:
        return None
    tailoring_session.blocks = blocks
    session.commit()
    session.refresh(tailoring_session)
    return tailoring_session