from sqlalchemy.orm import Session

from core.db.models import ScoringFactor


def create_scoring_factor(
    session: Session, text: str, direction: str, weight: int = 1, order: int = 0
) -> ScoringFactor:
    factor = ScoringFactor(text=text, direction=direction, weight=weight, order=order)
    session.add(factor)
    session.commit()
    session.refresh(factor)
    return factor


def get_scoring_factor(session: Session, scoring_factor_id: int) -> ScoringFactor | None:
    return session.get(ScoringFactor, scoring_factor_id)


def list_scoring_factors(session: Session) -> list[ScoringFactor]:
    return session.query(ScoringFactor).order_by(ScoringFactor.order.asc()).all()


def update_scoring_factor(
    session: Session,
    scoring_factor_id: int,
    text: str | None = None,
    direction: str | None = None,
    weight: int | None = None,
    order: int | None = None,
) -> ScoringFactor | None:
    factor = session.get(ScoringFactor, scoring_factor_id)
    if factor is None:
        return None
    if text is not None:
        factor.text = text
    if direction is not None:
        factor.direction = direction
    if weight is not None:
        factor.weight = weight
    if order is not None:
        factor.order = order
    session.commit()
    session.refresh(factor)
    return factor


def delete_scoring_factor(session: Session, scoring_factor_id: int) -> bool:
    factor = session.get(ScoringFactor, scoring_factor_id)
    if factor is None:
        return False
    session.delete(factor)
    session.commit()
    return True