from sqlalchemy.orm import Session

from core.db.models import GapItem


def bulk_create_gap_items(session: Session, session_id: int, items: list[dict]) -> list[GapItem]:
    created = []
    for item in items:
        suggested_paths = item.get("suggested_field_paths") or []
        row = GapItem(
            session_id=session_id,
            text=item["text"],
            category=item.get("category"),
            status=item["status"],
            priority=item.get("priority"),
            source=item.get("source"),
            original_field_path=item.get("original_field_path"),
            suggested_field_paths=suggested_paths,
            suggested_reason=item.get("suggested_reason"),
            assigned_field_paths=list(suggested_paths) if item["status"] == "match" else [],
            recommend_keep=item.get("recommend_keep"),
            included=item["status"] == "match",
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def list_gap_items_for_session(session: Session, session_id: int) -> list[GapItem]:
    return (
        session.query(GapItem)
        .filter(GapItem.session_id == session_id)
        .order_by(GapItem.status.asc(), GapItem.id.asc())
        .all()
    )


def clear_gap_items_for_session(session: Session, session_id: int) -> None:
    session.query(GapItem).filter(GapItem.session_id == session_id).delete(synchronize_session=False)
    session.commit()


def create_custom_gap_item(session: Session, session_id: int, text: str, field_path: str) -> GapItem:
    item = GapItem(
        session_id=session_id,
        text=text,
        category="skill",
        status="can_add",
        source="profile",
        assigned_field_paths=[field_path],
        included=True,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def toggle_gap_item_location(session: Session, gap_item_id: int, field_path: str) -> GapItem | None:
    item = session.get(GapItem, gap_item_id)
    if item is None:
        return None
    current = list(item.assigned_field_paths or [])
    if field_path in current:
        current.remove(field_path)
    else:
        current.append(field_path)
    item.assigned_field_paths = current
    item.included = len(current) > 0
    if item.status == "miss" and current:
        item.status = "can_add"
    session.commit()
    session.refresh(item)
    return item


def set_block_comment(session: Session, session_id: int, block_path: str, comment: str) -> None:
    from core.db.models import TailoringSession

    tailoring_session = session.get(TailoringSession, session_id)
    if tailoring_session is None:
        return
    comments = dict(tailoring_session.block_comments or {})
    if comment.strip():
        comments[block_path] = comment
    else:
        comments.pop(block_path, None)
    tailoring_session.block_comments = comments
    session.commit()


def mark_gap_analysis_ready(session: Session, session_id: int) -> None:
    from core.db.models import TailoringSession

    tailoring_session = session.get(TailoringSession, session_id)
    if tailoring_session is None:
        return
    tailoring_session.gap_analysis_ready = True
    session.commit()


def set_resume_items(session: Session, session_id: int, resume_items: list[dict]) -> None:
    from core.db.models import TailoringSession

    tailoring_session = session.get(TailoringSession, session_id)
    if tailoring_session is None:
        return
    tailoring_session.resume_items = resume_items
    session.commit()