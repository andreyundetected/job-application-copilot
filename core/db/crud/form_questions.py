from sqlalchemy.orm import Session

from core.db.models import FormQuestion


def create_form_question(
    session: Session,
    application_id: int,
    question_text: str,
    answer_type: str,
    category: str | None = None,
    answer_text: str | None = None,
    answer_file_path: str | None = None,
    needs_manual_input: bool = False,
    order: int = 0,
) -> FormQuestion:
    question = FormQuestion(
        application_id=application_id,
        question_text=question_text,
        answer_type=answer_type,
        category=category,
        answer_text=answer_text,
        answer_file_path=answer_file_path,
        needs_manual_input=needs_manual_input,
        order=order,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def bulk_create_form_questions(
    session: Session, application_id: int, questions: list[dict]
) -> list[FormQuestion]:
    created = []
    for index, question in enumerate(questions):
        row = FormQuestion(
            application_id=application_id,
            question_text=question["question_text"],
            answer_type=question["answer_type"],
            category=question.get("category"),
            answer_text=question.get("answer_text"),
            needs_manual_input=question.get("needs_manual_input", False),
            order=index,
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def get_form_question(session: Session, form_question_id: int) -> FormQuestion | None:
    return session.get(FormQuestion, form_question_id)


def list_form_questions_for_application(
    session: Session, application_id: int
) -> list[FormQuestion]:
    return (
        session.query(FormQuestion)
        .filter(FormQuestion.application_id == application_id)
        .order_by(FormQuestion.order.asc())
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


def delete_form_question(session: Session, form_question_id: int) -> bool:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return False
    session.delete(question)
    session.commit()
    return True