from sqlalchemy.orm import Session

from core.db.models import FormQuestionMessage


def create_question_message(
    session: Session, question_id: int, role: str, text: str
) -> FormQuestionMessage:
    message = FormQuestionMessage(question_id=question_id, role=role, text=text)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_question_messages(session: Session, question_id: int) -> list[FormQuestionMessage]:
    return (
        session.query(FormQuestionMessage)
        .filter(FormQuestionMessage.question_id == question_id)
        .order_by(FormQuestionMessage.created_at.asc())
        .all()
    )