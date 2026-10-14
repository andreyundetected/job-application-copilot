from sqlalchemy.orm import Session

from core.db.models import TitleRejection

PROMPT_LIMIT = 40


def add_title_rejection(
    session: Session,
    original: str,
    rejected: str,
    comment: str,
    kind: str = "",
    session_id: int | None = None,
) -> TitleRejection:
    row = TitleRejection(
        original=original[:500],
        rejected=rejected[:500],
        comment=(comment or "")[:2000],
        kind=(kind or "")[:16],
        session_id=session_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_title_rejections(session: Session, session_id: int | None = None) -> list[TitleRejection]:
    query = session.query(TitleRejection)
    if session_id is None:
        query = query.filter(TitleRejection.session_id.is_(None))
    else:
        query = query.filter(
            (TitleRejection.session_id.is_(None)) | (TitleRejection.session_id == session_id)
        )
    rows = query.order_by(TitleRejection.id.desc()).limit(PROMPT_LIMIT).all()
    return list(reversed(rows))


def delete_title_rejection(session: Session, rejection_id: int) -> bool:
    row = session.get(TitleRejection, rejection_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True