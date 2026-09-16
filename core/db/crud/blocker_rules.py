from sqlalchemy.orm import Session

from core.db.models import BlockerRule


def create_blocker_rule(session: Session, text: str, order: int = 0) -> BlockerRule:
    rule = BlockerRule(text=text, order=order)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def get_blocker_rule(session: Session, blocker_rule_id: int) -> BlockerRule | None:
    return session.get(BlockerRule, blocker_rule_id)


def list_blocker_rules(session: Session) -> list[BlockerRule]:
    return session.query(BlockerRule).order_by(BlockerRule.order.asc()).all()


def update_blocker_rule(
    session: Session, blocker_rule_id: int, text: str | None = None, order: int | None = None
) -> BlockerRule | None:
    rule = session.get(BlockerRule, blocker_rule_id)
    if rule is None:
        return None
    if text is not None:
        rule.text = text
    if order is not None:
        rule.order = order
    session.commit()
    session.refresh(rule)
    return rule


def delete_blocker_rule(session: Session, blocker_rule_id: int) -> bool:
    rule = session.get(BlockerRule, blocker_rule_id)
    if rule is None:
        return False
    session.delete(rule)
    session.commit()
    return True