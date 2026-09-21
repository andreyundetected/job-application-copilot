import pytest

from core.db.crud import automation_base_questions as base_questions_crud


@pytest.mark.db
def test_create_and_list_base_questions_ordered(db_session):
    base_questions_crud.create_automation_base_question(db_session, "First question")
    base_questions_crud.create_automation_base_question(db_session, "Second question")

    questions = base_questions_crud.list_automation_base_questions(db_session)

    assert [q.question_text for q in questions] == ["First question", "Second question"]
    assert questions[0].order == 0
    assert questions[1].order == 1


@pytest.mark.db
def test_delete_base_question(db_session):
    question = base_questions_crud.create_automation_base_question(db_session, "To delete")

    deleted = base_questions_crud.delete_automation_base_question(db_session, question.id)
    remaining = base_questions_crud.list_automation_base_questions(db_session)

    assert deleted is True
    assert remaining == []


@pytest.mark.db
def test_delete_base_question_not_found(db_session):
    assert base_questions_crud.delete_automation_base_question(db_session, 999) is False