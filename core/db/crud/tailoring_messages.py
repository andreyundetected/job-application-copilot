from sqlalchemy.orm import Session

from core.db.models import TailoringMessage


def create_tailoring_message(
    session: Session, session_id: int, role: str, text: str
) -> TailoringMessage:
    message = TailoringMessage(session_id=session_id, role=role, text=text)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_tailoring_messages(session: Session, session_id: int) -> list[TailoringMessage]:
    return (
        session.query(TailoringMessage)
        .filter(TailoringMessage.session_id == session_id)
        .order_by(TailoringMessage.created_at.asc())
        .all()
    )