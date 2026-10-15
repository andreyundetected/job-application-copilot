import pytest

from core.db.crud import automation_settings as automation_settings_crud


@pytest.mark.db
def test_resume_apply_defaults_are_on_and_letter_is_off(db_session):
    settings = automation_settings_crud.upsert_automation_settings(db_session)

    assert settings.auto_apply_title_main is True
    assert settings.auto_apply_exp_titles is True
    assert settings.auto_apply_summary is True
    assert settings.auto_apply_skills is True
    assert settings.auto_letter_master_enabled is False


@pytest.mark.db
def test_single_apply_flag_can_be_turned_off_without_touching_others(db_session):
    automation_settings_crud.upsert_automation_settings(db_session)

    updated = automation_settings_crud.upsert_automation_settings(db_session, auto_apply_summary=False)

    assert updated.auto_apply_summary is False
    assert updated.auto_apply_title_main is True
    assert updated.auto_apply_exp_titles is True
    assert updated.auto_apply_skills is True


@pytest.mark.db
def test_letter_master_toggle_is_independent_from_resume_master(db_session):
    automation_settings_crud.upsert_automation_settings(db_session, auto_tailor_master_enabled=True)

    updated = automation_settings_crud.upsert_automation_settings(db_session, auto_letter_master_enabled=True)
    assert updated.auto_tailor_master_enabled is True
    assert updated.auto_letter_master_enabled is True

    updated = automation_settings_crud.upsert_automation_settings(db_session, auto_tailor_master_enabled=False)
    assert updated.auto_tailor_master_enabled is False
    assert updated.auto_letter_master_enabled is True