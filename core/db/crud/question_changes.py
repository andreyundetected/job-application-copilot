from sqlalchemy.orm import Session

from core.db.models import QuestionChange


def create_question_change(
    session: Session,
    question_id: int,
    chat_message_id: int | None,
    original_text: str | None,
    proposed_text: str,
) -> QuestionChange:
    change = QuestionChange(
        question_id=question_id,
        chat_message_id=chat_message_id,
        original_text=original_text,
        proposed_text=proposed_text,
        status="pending",
    )
    session.add(change)
    session.commit()
    session.refresh(change)
    return change


def get_question_change(session: Session, change_id: int) -> QuestionChange | None:
    return session.get(QuestionChange, change_id)


def resolve_question_change(session: Session, change_id: int, status: str) -> QuestionChange | None:
    change = session.get(QuestionChange, change_id)
    if change is None:
        return None
    change.status = status
    session.commit()
    session.refresh(change)
    return change


def list_changes_for_application(session: Session, application_id: int) -> list[QuestionChange]:
    return (
        session.query(QuestionChange)
        .join(QuestionChange.question)
        .filter(QuestionChange.question.has(application_id=application_id))
        .order_by(QuestionChange.created_at.asc())
        .all()
    )