import pytest

from core.db.crud import automation_settings as automation_settings_crud


@pytest.mark.db
def test_get_automation_settings_returns_none_when_empty(db_session):
    assert automation_settings_crud.get_automation_settings(db_session) is None


@pytest.mark.db
def test_upsert_automation_settings_creates_with_defaults(db_session):
    settings = automation_settings_crud.upsert_automation_settings(db_session)

    assert settings.min_score_to_proceed == 6
    assert settings.max_score_to_archive == 3
    assert settings.quick_filter_enabled is True
    assert settings.auto_tailor_soft_enabled is True
    assert settings.auto_tailor_medium_enabled is True
    assert settings.serpent_num_per_query == 30
    assert settings.default_time_range == "w1"
    assert settings.max_query_words == 32
    assert settings.target_sites == [
        "boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
    ]
    assert settings.saved_queries == []


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
    automation_settings_crud.upsert_automation_settings(db_session, max_query_words=20, default_time_range="d1")

    updated = automation_settings_crud.upsert_automation_settings(db_session, min_score_to_proceed=8)

    assert updated.max_query_words == 20
    assert updated.default_time_range == "d1"
    assert updated.min_score_to_proceed == 8


@pytest.mark.db
def test_upsert_automation_settings_updates_target_sites(db_session):
    automation_settings_crud.upsert_automation_settings(db_session)

    updated = automation_settings_crud.upsert_automation_settings(
        db_session, target_sites=["boards.greenhouse.io", "example.com"]
    )

    assert updated.target_sites == ["boards.greenhouse.io", "example.com"]


@pytest.mark.db
def test_upsert_automation_settings_stores_saved_queries_as_flat_strings(db_session):
    queries = ['(site:example.com) ("AI Engineer" OR "LLM Engineer")']

    settings = automation_settings_crud.upsert_automation_settings(db_session, saved_queries=queries)

    assert settings.saved_queries == queries


@pytest.mark.db
def test_get_automation_settings_returns_lowest_id_when_duplicates_exist(db_session):
    from core.db.models import AutomationSettings

    older = AutomationSettings(min_score_to_proceed=5)
    newer = AutomationSettings(min_score_to_proceed=9)
    db_session.add_all([older, newer])
    db_session.commit()

    result = automation_settings_crud.get_automation_settings(db_session)

    assert result.id == min(older.id, newer.id)