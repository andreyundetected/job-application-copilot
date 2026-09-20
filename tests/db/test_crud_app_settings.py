import pytest

from core.db.crud import app_settings as app_settings_crud


@pytest.mark.db
def test_upsert_app_settings_creates_with_defaults(db_session):
    settings = app_settings_crud.upsert_app_settings(db_session)

    assert settings.pregenerate_enabled is False
    assert settings.pregenerate_min_score == 7
    assert settings.auto_answer_questions_enabled is True


@pytest.mark.db
def test_upsert_app_settings_updates_auto_answer_flag(db_session):
    app_settings_crud.upsert_app_settings(db_session)

    updated = app_settings_crud.upsert_app_settings(db_session, auto_answer_questions_enabled=False)

    assert updated.auto_answer_questions_enabled is False


@pytest.mark.db
def test_upsert_app_settings_preserves_other_fields_when_updating_auto_answer(db_session):
    app_settings_crud.upsert_app_settings(db_session, pregenerate_enabled=True, pregenerate_min_score=9)

    updated = app_settings_crud.upsert_app_settings(db_session, auto_answer_questions_enabled=False)

    assert updated.pregenerate_enabled is True
    assert updated.pregenerate_min_score == 9
    assert updated.auto_answer_questions_enabled is False


@pytest.mark.db
def test_get_app_settings_returns_none_when_empty(db_session):
    assert app_settings_crud.get_app_settings(db_session) is None