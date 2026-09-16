import pytest

from core.db.crud import candidate_profile as candidate_profile_crud


@pytest.mark.db
def test_upsert_candidate_profile_creates_when_missing(db_session):
    profile = candidate_profile_crud.upsert_candidate_profile(
        db_session,
        email="sample@example.com",
        github_url="github.com/sampleuser",
        linkedin_url="linkedin.com/in/sampleuser",
        extra_links=["example.com/portfolio"],
        extra_info="Sample extra info.",
    )

    assert profile.id is not None
    assert profile.email == "sample@example.com"
    assert profile.extra_links == ["example.com/portfolio"]


@pytest.mark.db
def test_upsert_candidate_profile_updates_existing(db_session):
    candidate_profile_crud.upsert_candidate_profile(db_session, email="old@example.com")

    updated = candidate_profile_crud.upsert_candidate_profile(db_session, email="new@example.com")

    all_profiles = db_session.query(type(updated)).all()
    assert len(all_profiles) == 1
    assert updated.email == "new@example.com"


@pytest.mark.db
def test_get_candidate_profile_returns_none_when_empty(db_session):
    result = candidate_profile_crud.get_candidate_profile(db_session)

    assert result is None