import pytest

from core.db.crud import blocker_rules as blocker_rules_crud


@pytest.mark.db
def test_create_and_list_blocker_rules_ordered(db_session):
    blocker_rules_crud.create_blocker_rule(db_session, text="Second rule", order=2)
    blocker_rules_crud.create_blocker_rule(db_session, text="First rule", order=1)

    rules = blocker_rules_crud.list_blocker_rules(db_session)

    assert [rule.text for rule in rules] == ["First rule", "Second rule"]


@pytest.mark.db
def test_update_blocker_rule(db_session):
    rule = blocker_rules_crud.create_blocker_rule(db_session, text="Original text")

    updated = blocker_rules_crud.update_blocker_rule(
        db_session, rule.id, text="Updated text"
    )

    assert updated.text == "Updated text"


@pytest.mark.db
def test_delete_blocker_rule(db_session):
    rule = blocker_rules_crud.create_blocker_rule(db_session, text="To delete")

    deleted = blocker_rules_crud.delete_blocker_rule(db_session, rule.id)
    missing = blocker_rules_crud.get_blocker_rule(db_session, rule.id)

    assert deleted is True
    assert missing is None