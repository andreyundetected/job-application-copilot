import pytest

from core.db.crud import applications as applications_crud
from core.db.crud import form_questions as form_questions_crud
from core.db.crud import jobs as jobs_crud


def _make_application(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    return applications_crud.create_application(db_session, job_posting_id=job.id)


@pytest.mark.db
def test_create_form_question(db_session):
    application = _make_application(db_session)

    question = form_questions_crud.create_form_question(
        db_session,
        application_id=application.id,
        question_text="Sample question?",
        answer_type="text",
    )

    assert question.id is not None
    assert question.answer_text is None


@pytest.mark.db
def test_update_form_question_answer(db_session):
    application = _make_application(db_session)
    question = form_questions_crud.create_form_question(
        db_session,
        application_id=application.id,
        question_text="Sample question?",
        answer_type="text",
    )

    updated = form_questions_crud.update_form_question_answer(
        db_session, question.id, answer_text="Sample answer."
    )

    assert updated.answer_text == "Sample answer."


@pytest.mark.db
def test_list_form_questions_for_application(db_session):
    application = _make_application(db_session)
    form_questions_crud.create_form_question(
        db_session,
        application_id=application.id,
        question_text="Q1",
        answer_type="text",
    )
    form_questions_crud.create_form_question(
        db_session,
        application_id=application.id,
        question_text="Q2",
        answer_type="file",
    )

    results = form_questions_crud.list_form_questions_for_application(
        db_session, application.id
    )

    assert len(results) == 2