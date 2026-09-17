from sqlalchemy.orm import Session

from core.db.models import TailoringChange


def bulk_create_tailoring_changes(
    session: Session, evaluation_id: int, changes: list[dict]
) -> list[TailoringChange]:
    created = []
    for index, change in enumerate(changes):
        row = TailoringChange(
            evaluation_id=evaluation_id,
            level=change["level"],
            change_type=change["change_type"],
            target_ref=change.get("target_ref"),
            original_text=change.get("original_text"),
            proposed_text=change["proposed_text"],
            status="pending",
            order=index,
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def bulk_create_session_changes(
    tailoring_session_db_session: Session,
    session_id: int,
    message_id: int,
    changes: list[dict],
) -> list[TailoringChange]:
    created = []
    for index, change in enumerate(changes):
        row = TailoringChange(
            session_id=session_id,
            message_id=message_id,
            level=change["level"],
            change_type=change["change_type"],
            field_path=change["field_path"],
            original_text=change.get("original_text"),
            proposed_text=change["proposed_text"],
            proposed_content=change.get("proposed_content"),
            status="pending",
            order=index,
        )
        tailoring_session_db_session.add(row)
        created.append(row)
    tailoring_session_db_session.commit()
    for row in created:
        tailoring_session_db_session.refresh(row)
    return created


def list_tailoring_changes_for_session(session: Session, session_id: int) -> list[TailoringChange]:
    return (
        session.query(TailoringChange)
        .filter(TailoringChange.session_id == session_id)
        .order_by(TailoringChange.order.asc())
        .all()
    )


def get_tailoring_change(session: Session, change_id: int) -> TailoringChange | None:
    return session.get(TailoringChange, change_id)


def list_tailoring_changes_for_evaluation(
    session: Session, evaluation_id: int, level: str | None = None
) -> list[TailoringChange]:
    query = session.query(TailoringChange).filter(
        TailoringChange.evaluation_id == evaluation_id
    )
    if level is not None:
        query = query.filter(TailoringChange.level == level)
    return query.order_by(TailoringChange.order.asc()).all()


def resolve_tailoring_change(
    session: Session, change_id: int, status: str, final_text: str | None = None
) -> TailoringChange | None:
    change = session.get(TailoringChange, change_id)
    if change is None:
        return None
    change.status = status
    change.final_text = final_text if final_text is not None else change.proposed_text
    session.commit()
    session.refresh(change)
    return change


def supersede_pending_changes(
    session: Session, session_id: int, field_paths: set[str]
) -> list[TailoringChange]:
    if not field_paths:
        return []

    matches = (
        session.query(TailoringChange)
        .filter(
            TailoringChange.session_id == session_id,
            TailoringChange.status == "pending",
            TailoringChange.field_path.in_(field_paths),
        )
        .all()
    )

    for change in matches:
        change.status = "superseded"

    session.commit()
    for change in matches:
        session.refresh(change)

    return matches


def supersede_pending_changes_by_original(
    session: Session, session_id: int, originals: set[str]
) -> list[TailoringChange]:
    if not originals:
        return []

    matches = (
        session.query(TailoringChange)
        .filter(
            TailoringChange.session_id == session_id,
            TailoringChange.status == "pending",
            TailoringChange.original_text.in_(originals),
        )
        .all()
    )

    for change in matches:
        change.status = "superseded"

    session.commit()
    for change in matches:
        session.refresh(change)

    return matches