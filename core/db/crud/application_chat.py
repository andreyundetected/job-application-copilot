from sqlalchemy.orm import Session

from core.db.models import ApplicationChatMessage


def create_chat_message(
    session: Session,
    application_id: int,
    role: str,
    text: str,
    referenced_question_id: int | None = None,
) -> ApplicationChatMessage:
    message = ApplicationChatMessage(
        application_id=application_id,
        role=role,
        text=text,
        referenced_question_id=referenced_question_id,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_chat_messages(session: Session, application_id: int) -> list[ApplicationChatMessage]:
    return (
        session.query(ApplicationChatMessage)
        .filter(ApplicationChatMessage.application_id == application_id)
        .order_by(ApplicationChatMessage.created_at.asc())
        .all()
    )