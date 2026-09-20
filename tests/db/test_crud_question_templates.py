import pytest

from core.db.crud import question_templates as question_templates_crud


@pytest.mark.db
def test_create_and_list_question_templates_ordered(db_session):
    question_templates_crud.create_question_template(
        db_session, label="First", trigger_phrases=["why us"], instructions="Keep it short."
    )
    question_templates_crud.create_question_template(
        db_session, label="Second", trigger_phrases=["greatest weakness"], instructions="Be honest."
    )

    templates = question_templates_crud.list_question_templates(db_session)

    assert [t.label for t in templates] == ["First", "Second"]
    assert templates[0].order == 0
    assert templates[1].order == 1


@pytest.mark.db
def test_delete_question_template(db_session):
    template = question_templates_crud.create_question_template(
        db_session, label="To delete", trigger_phrases=["remove me"], instructions="n/a"
    )

    deleted = question_templates_crud.delete_question_template(db_session, template.id)
    missing = question_templates_crud.get_question_template(db_session, template.id)

    assert deleted is True
    assert missing is None


@pytest.mark.db
def test_delete_question_template_not_found(db_session):
    assert question_templates_crud.delete_question_template(db_session, 999) is False


@pytest.mark.db
def test_match_question_template_finds_case_insensitive_substring(db_session):
    template = question_templates_crud.create_question_template(
        db_session, label="Why us", trigger_phrases=["why do you want to work here"], instructions="Keep it short."
    )
    templates = question_templates_crud.list_question_templates(db_session)

    match = question_templates_crud.match_question_template(
        templates, "So, Why Do You Want To Work Here at our company?"
    )

    assert match is not None
    assert match.id == template.id


@pytest.mark.db
def test_match_question_template_returns_none_when_no_phrase_matches(db_session):
    question_templates_crud.create_question_template(
        db_session, label="Why us", trigger_phrases=["why do you want to work here"], instructions="Keep it short."
    )
    templates = question_templates_crud.list_question_templates(db_session)

    match = question_templates_crud.match_question_template(templates, "Describe a recent project you led.")

    assert match is None


@pytest.mark.db
def test_match_question_template_returns_first_matching_template_in_order(db_session):
    first = question_templates_crud.create_question_template(
        db_session, label="First", trigger_phrases=["project"], instructions="a"
    )
    question_templates_crud.create_question_template(
        db_session, label="Second", trigger_phrases=["project"], instructions="b"
    )
    templates = question_templates_crud.list_question_templates(db_session)

    match = question_templates_crud.match_question_template(templates, "Describe a project you led.")

    assert match.id == first.id