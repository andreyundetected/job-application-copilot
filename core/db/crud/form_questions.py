from sqlalchemy.orm import Session

from core.db.models import FormQuestion


def create_form_question(
    session: Session,
    application_id: int,
    question_text: str,
    answer_type: str,
    category: str | None = None,
    options: list | None = None,
    selected_option: str | None = None,
    char_limit: int | None = None,
    answer_text: str | None = None,
    answer_file_path: str | None = None,
    needs_manual_input: bool = False,
    flag_reason: str | None = None,
    order: int = 0,
) -> FormQuestion:
    question = FormQuestion(
        application_id=application_id,
        question_text=question_text,
        answer_type=answer_type,
        category=category,
        options=options,
        selected_option=selected_option,
        char_limit=char_limit,
        answer_text=answer_text,
        answer_file_path=answer_file_path,
        needs_manual_input=needs_manual_input,
        flag_reason=flag_reason,
        order=order,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def bulk_create_form_questions(
    session: Session, application_id: int, questions: list[dict], order_offset: int = 0
) -> list[FormQuestion]:
    created = []
    for index, question in enumerate(questions):
        row = FormQuestion(
            application_id=application_id,
            question_text=question["question_text"],
            answer_type=question["answer_type"],
            category=question.get("category"),
            options=question.get("options"),
            selected_option=question.get("selected_option"),
            char_limit=question.get("char_limit"),
            answer_text=question.get("answer_text"),
            needs_manual_input=question.get("needs_manual_input", False),
            flag_reason=question.get("flag_reason"),
            order=order_offset + index,
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
    selected_option: str | None = None,
) -> FormQuestion | None:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return None
    if answer_text is not None:
        question.answer_text = answer_text
    if answer_file_path is not None:
        question.answer_file_path = answer_file_path
    if selected_option is not None:
        question.selected_option = selected_option
    session.commit()
    session.refresh(question)
    return question


def set_question_generation_result(
    session: Session,
    form_question_id: int,
    answer_text: str | None,
    selected_option: str | None,
    needs_manual_input: bool,
    flag_reason: str | None,
) -> FormQuestion | None:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return None
    question.answer_text = answer_text
    question.selected_option = selected_option
    question.needs_manual_input = needs_manual_input
    question.flag_reason = flag_reason
    session.commit()
    session.refresh(question)
    return question


def set_question_pending_task(
    session: Session, form_question_id: int, task_id: int | None
) -> FormQuestion | None:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return None
    question.pending_task_id = task_id
    session.commit()
    session.refresh(question)
    return question


def update_form_question_char_limit(
    session: Session, form_question_id: int, char_limit: int | None
) -> FormQuestion | None:
    question = session.get(FormQuestion, form_question_id)
    if question is None:
        return None
    question.char_limit = char_limit
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