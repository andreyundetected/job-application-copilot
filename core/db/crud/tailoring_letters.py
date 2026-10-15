import datetime

from sqlalchemy.orm import Session

from core.db.models import TailoringLetter


def get_letter(session: Session, session_id: int) -> TailoringLetter | None:
    return session.query(TailoringLetter).filter(TailoringLetter.session_id == session_id).first()


def save_letter(
    session: Session,
    session_id: int,
    content: str,
    notes: str = "",
    comment: str | None = None,
) -> TailoringLetter:
    row = get_letter(session, session_id)
    if row is None:
        row = TailoringLetter(session_id=session_id)
        session.add(row)
    row.content = content
    row.notes = (notes or "")[:2000]
    if comment is not None:
        row.comment = comment[:2000]
    row.updated_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(row)
    return row