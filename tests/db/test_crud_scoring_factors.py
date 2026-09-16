import pytest

from core.db.crud import scoring_factors as scoring_factors_crud


@pytest.mark.db
def test_create_and_list_scoring_factors_ordered(db_session):
    scoring_factors_crud.create_scoring_factor(
        db_session, text="Second factor", direction="minus", weight=1, order=2
    )
    scoring_factors_crud.create_scoring_factor(
        db_session, text="First factor", direction="plus", weight=2, order=1
    )

    factors = scoring_factors_crud.list_scoring_factors(db_session)

    assert [factor.text for factor in factors] == ["First factor", "Second factor"]


@pytest.mark.db
def test_update_scoring_factor(db_session):
    factor = scoring_factors_crud.create_scoring_factor(
        db_session, text="Original", direction="plus", weight=1
    )

    updated = scoring_factors_crud.update_scoring_factor(
        db_session, factor.id, weight=3
    )

    assert updated.weight == 3


@pytest.mark.db
def test_delete_scoring_factor(db_session):
    factor = scoring_factors_crud.create_scoring_factor(
        db_session, text="To delete", direction="minus", weight=1
    )

    deleted = scoring_factors_crud.delete_scoring_factor(db_session, factor.id)
    missing = scoring_factors_crud.get_scoring_factor(db_session, factor.id)

    assert deleted is True
    assert missing is None