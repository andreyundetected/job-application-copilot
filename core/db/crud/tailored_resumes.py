from sqlalchemy.orm import Session

from core.db.models import TailoredResume


def create_tailored_resume(
    session: Session,
    evaluation_id: int,
    content: list,
    keywords_used: dict | None = None,
    docx_path: str | None = None,
) -> TailoredResume:
    tailored = TailoredResume(
        evaluation_id=evaluation_id,
        content=content,
        keywords_used=keywords_used,
        docx_path=docx_path,
    )
    session.add(tailored)
    session.commit()
    session.refresh(tailored)
    return tailored


def get_tailored_resume(
    session: Session, tailored_resume_id: int
) -> TailoredResume | None:
    return session.get(TailoredResume, tailored_resume_id)


def update_tailored_resume_docx_path(
    session: Session, tailored_resume_id: int, docx_path: str
) -> TailoredResume | None:
    tailored = session.get(TailoredResume, tailored_resume_id)
    if tailored is None:
        return None
    tailored.docx_path = docx_path
    session.commit()
    session.refresh(tailored)
    return tailored


def list_tailored_resumes_for_evaluation(
    session: Session, evaluation_id: int
) -> list[TailoredResume]:
    return (
        session.query(TailoredResume)
        .filter(TailoredResume.evaluation_id == evaluation_id)
        .order_by(TailoredResume.created_at.desc())
        .all()
    )