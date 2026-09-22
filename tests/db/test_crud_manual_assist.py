import pytest

from core.db.crud import manual_assist as manual_assist_crud


@pytest.mark.db
def test_manual_assist_permissions_independent_from_automation(db_session):
    from core.db.crud import tailoring_permissions as automation_permissions_crud

    automation_permissions_crud.set_tailoring_permission(db_session, level="soft", change_type="title", auto_apply=True)

    assert automation_permissions_crud.is_auto_apply(db_session, "soft", "title") is True
    assert manual_assist_crud.manual_assist_is_auto_apply(db_session, "soft", "title") is False


@pytest.mark.db
def test_set_and_read_manual_assist_permission(db_session):
    manual_assist_crud.set_manual_assist_tailoring_permission(db_session, level="soft", change_type="skills", auto_apply=True)

    assert manual_assist_crud.manual_assist_is_auto_apply(db_session, "soft", "skills") is True
    assert manual_assist_crud.manual_assist_level_has_auto_apply(db_session, "soft") is True
    assert manual_assist_crud.manual_assist_level_has_auto_apply(db_session, "medium") is False


@pytest.mark.db
def test_manual_assist_base_questions_independent_from_automation(db_session):
    from core.db.crud import automation_base_questions as automation_questions_crud

    automation_questions_crud.create_automation_base_question(db_session, "Automation-only question")
    manual_assist_crud.create_manual_assist_base_question(db_session, "Manual-only question")

    automation_questions = automation_questions_crud.list_automation_base_questions(db_session)
    manual_questions = manual_assist_crud.list_manual_assist_base_questions(db_session)

    assert [q.question_text for q in automation_questions] == ["Automation-only question"]
    assert [q.question_text for q in manual_questions] == ["Manual-only question"]


@pytest.mark.db
def test_delete_manual_assist_base_question(db_session):
    question = manual_assist_crud.create_manual_assist_base_question(db_session, "To delete")

    deleted = manual_assist_crud.delete_manual_assist_base_question(db_session, question.id)
    remaining = manual_assist_crud.list_manual_assist_base_questions(db_session)

    assert deleted is True
    assert remaining == []


@pytest.mark.db
def test_delete_manual_assist_base_question_not_found(db_session):
    assert manual_assist_crud.delete_manual_assist_base_question(db_session, 999) is False