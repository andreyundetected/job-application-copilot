import pytest

from core.db.crud import tailoring_permissions as tailoring_permissions_crud


@pytest.mark.db
def test_seed_default_tailoring_permissions_populates_expected_matrix(db_session):
    tailoring_permissions_crud.seed_default_tailoring_permissions(db_session)

    permissions = tailoring_permissions_crud.list_tailoring_permissions(db_session)
    as_map = {(p.level, p.change_type): p.auto_apply for p in permissions}

    assert as_map == {
        ("soft", "title"): True,
        ("soft", "company_name"): True,
        ("soft", "skills"): True,
        ("medium", "summary"): True,
        ("medium", "bullet"): False,
    }


@pytest.mark.db
def test_seed_default_tailoring_permissions_is_noop_when_rows_exist(db_session):
    tailoring_permissions_crud.set_tailoring_permission(
        db_session, level="soft", change_type="title", auto_apply=False
    )

    tailoring_permissions_crud.seed_default_tailoring_permissions(db_session)

    permissions = tailoring_permissions_crud.list_tailoring_permissions(db_session)
    assert len(permissions) == 1
    assert permissions[0].auto_apply is False


@pytest.mark.db
def test_is_auto_apply_reflects_seeded_defaults(db_session):
    tailoring_permissions_crud.seed_default_tailoring_permissions(db_session)

    assert tailoring_permissions_crud.is_auto_apply(db_session, "soft", "skills") is True
    assert tailoring_permissions_crud.is_auto_apply(db_session, "medium", "bullet") is False
    assert tailoring_permissions_crud.is_auto_apply(db_session, "medium", "unknown_type") is False


@pytest.mark.db
def test_level_has_auto_apply_true_when_any_change_type_permitted(db_session):
    tailoring_permissions_crud.seed_default_tailoring_permissions(db_session)

    assert tailoring_permissions_crud.level_has_auto_apply(db_session, "soft") is True
    assert tailoring_permissions_crud.level_has_auto_apply(db_session, "medium") is True


@pytest.mark.db
def test_level_has_auto_apply_false_when_nothing_permitted(db_session):
    tailoring_permissions_crud.set_tailoring_permission(
        db_session, level="medium", change_type="bullet", auto_apply=False
    )
    tailoring_permissions_crud.set_tailoring_permission(
        db_session, level="medium", change_type="summary", auto_apply=False
    )

    assert tailoring_permissions_crud.level_has_auto_apply(db_session, "medium") is False


@pytest.mark.db
def test_level_has_auto_apply_false_for_empty_matrix(db_session):
    assert tailoring_permissions_crud.level_has_auto_apply(db_session, "soft") is False