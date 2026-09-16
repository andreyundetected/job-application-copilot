from sqlalchemy.orm import Session

from core.db.models import FormQuestion


def create_form_question(
    session: Session,
    application_id: int,
    question_text: str,
    answer_type: str,
    answer_text: str | None = None,
    answer_file_path: str | None = None,
) -> FormQuestion:
    question = FormQuestion(
        application_id=application_id,
        question_text=question_text,
        answer_type=answer_type,
        answer_text=answer_text,
        answer_file_path=answer_file_path,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def get_form_question(session: Session, form_question_id: int) -> FormQuestion | None:
    return session.get(FormQuestion, form_question_id)


def list_form_questions_for_application(
    session: Session, application_id: int
) -> list[FormQuestion]:
    return (
        session.query(FormQuestion)
        .filter(FormQuestion.application_id == application_id)
        .all()
    )


def update_form_question_answer(
    session: Session,
    form_question_id: int,
    answer_text: str | None = None,
    answer_file_path: str | None = None,
) -> FormQuestion | None:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return None
    if answer_text is not None:
        question.answer_text = answer_text
    if answer_file_path is not None:
        question.answer_file_path = answer_file_path
    session.commit()
    session.refresh(question)
    return question