import pytest

from core.db.crud import candidate_profile as candidate_profile_crud


@pytest.mark.db
def test_letter_note_is_saved_and_trimmed(db_session):
    profile = candidate_profile_crud.update_letter_note(db_session, "  keep it direct  ")

    assert profile.letter_note == "keep it direct"


@pytest.mark.db
def test_blank_letter_note_clears_the_value(db_session):
    candidate_profile_crud.update_letter_note(db_session, "something")

    profile = candidate_profile_crud.update_letter_note(db_session, "   ")

    assert profile.letter_note is None


@pytest.mark.db
def test_letter_note_does_not_touch_other_profile_fields(db_session):
    candidate_profile_crud.upsert_candidate_profile(db_session, full_name="Sample Name", email="sample@example.com")

    profile = candidate_profile_crud.update_letter_note(db_session, "note")

    assert profile.full_name == "Sample Name"
    assert profile.email == "sample@example.com"