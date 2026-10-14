from sqlalchemy.orm import Session

from core.db.models import GapItem, KnownSkill
from core.gap_analysis.keywords import normalize_text

PROMOTABLE_STATUSES = ("unknown", "miss", "can_add")


def list_known_skills(session: Session) -> list[KnownSkill]:
    return session.query(KnownSkill).order_by(KnownSkill.text.asc()).all()


def add_known_skills(session: Session, texts: list[str]) -> int:
    existing = {row[0] for row in session.query(KnownSkill.text_norm).all()}
    created = 0
    for text in texts:
        cleaned = (text or "").strip()
        norm = normalize_text(cleaned)
        if not norm or norm in existing:
            continue
        session.add(KnownSkill(text=cleaned[:255], text_norm=norm[:255]))
        existing.add(norm)
        created += 1
    session.commit()
    return created


def delete_known_skill(session: Session, skill_id: int) -> bool:
    skill = session.get(KnownSkill, skill_id)
    if skill is None:
        return False
    session.delete(skill)
    session.commit()
    return True


def promote_unknown_gap_items(session: Session, session_id: int, texts: list[str]) -> list[GapItem]:
    norms = {normalize_text(text) for text in texts}
    items = (
        session.query(GapItem)
        .filter(GapItem.session_id == session_id, GapItem.status.in_(("unknown", "miss")))
        .all()
    )
    updated = []
    for item in items:
        if normalize_text(item.text) in norms:
            item.status = "can_add"
            updated.append(item)
    session.commit()
    for item in updated:
        session.refresh(item)
    return updated


def promote_gap_items(session: Session, session_id: int, entries: list[dict]) -> list[GapItem]:
    updated = []
    for entry in entries:
        item = session.get(GapItem, entry["id"])
        if item is None or item.session_id != session_id or item.status not in PROMOTABLE_STATUSES:
            continue
        cleaned = (entry.get("text") or "").strip()[:255]
        if cleaned and cleaned != item.text:
            item.text = cleaned
        item.status = "can_add"
        updated.append(item)
    session.commit()
    for item in updated:
        session.refresh(item)
    return updated