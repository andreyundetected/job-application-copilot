import pytest

from core.db.crud import automation_settings as automation_settings_crud


@pytest.mark.db
def test_get_automation_settings_returns_none_when_empty(db_session):
    result = automation_settings_crud.get_automation_settings(db_session)

    assert result is None


@pytest.mark.db
def test_upsert_automation_settings_creates_with_defaults(db_session):
    settings = automation_settings_crud.upsert_automation_settings(db_session)

    assert settings.min_score_to_proceed == 6
    assert settings.max_score_to_archive == 3
    assert settings.quick_filter_enabled is True
    assert settings.auto_tailor_soft_enabled is False
    assert settings.auto_tailor_medium_enabled is False
    assert settings.query_chunk_size == 8
    assert settings.serpent_num_per_query == 30
    assert settings.default_time_range == "w1"
    assert settings.saved_queries == []


@pytest.mark.db
def test_upsert_automation_settings_updates_serpent_num_per_query(db_session):
    automation_settings_crud.upsert_automation_settings(db_session)

    updated = automation_settings_crud.upsert_automation_settings(db_session, serpent_num_per_query=50)

    assert updated.serpent_num_per_query == 50


@pytest.mark.db
def test_upsert_automation_settings_updates_existing(db_session):
    automation_settings_crud.upsert_automation_settings(db_session, min_score_to_proceed=6)

    updated = automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=7, auto_tailor_soft_enabled=True
    )

    all_rows = db_session.query(type(updated)).all()
    assert len(all_rows) == 1
    assert updated.min_score_to_proceed == 7
    assert updated.auto_tailor_soft_enabled is True


@pytest.mark.db
def test_upsert_automation_settings_preserves_unspecified_fields(db_session):
    automation_settings_crud.upsert_automation_settings(
        db_session, query_chunk_size=5, default_time_range="d1"
    )

    updated = automation_settings_crud.upsert_automation_settings(db_session, min_score_to_proceed=8)

    assert updated.query_chunk_size == 5
    assert updated.default_time_range == "d1"
    assert updated.min_score_to_proceed == 8


@pytest.mark.db
def test_upsert_automation_settings_stores_saved_queries(db_session):
    presets = [{"label": "AI Engineer roles", "terms": ["AI Engineer", "LLM Engineer"]}]

    settings = automation_settings_crud.upsert_automation_settings(db_session, saved_queries=presets)

    assert settings.saved_queries == presets