from sqlalchemy.orm import Session

from core.db.models import TailoringPermission

DEFAULT_TAILORING_PERMISSIONS = [
    ("soft", "title", True),
    ("soft", "company_name", True),
    ("soft", "skills", True),
    ("medium", "summary", True),
    ("medium", "bullet", False),
]


def list_tailoring_permissions(session: Session) -> list[TailoringPermission]:
    return session.query(TailoringPermission).all()


def seed_default_tailoring_permissions(session: Session) -> None:
    """Populates the tailoring_permissions table with default auto-apply values,
    but only if the table is completely empty - never overwrites existing rows,
    including ones a user has already toggled off."""
    if session.query(TailoringPermission).first() is not None:
        return

    for level, change_type, auto_apply in DEFAULT_TAILORING_PERMISSIONS:
        session.add(TailoringPermission(level=level, change_type=change_type, auto_apply=auto_apply))
    session.commit()


def level_has_auto_apply(session: Session, level: str) -> bool:
    """True if at least one change_type under this level is set to auto-apply -
    used to decide whether to run soft/medium tailoring at all during automation,
    since there's no point calling the LLM for a level nothing will ever auto-apply."""
    return (
        session.query(TailoringPermission)
        .filter(TailoringPermission.level == level, TailoringPermission.auto_apply.is_(True))
        .first()
        is not None
    )


def is_auto_apply(session: Session, level: str, change_type: str) -> bool:
    permission = (
        session.query(TailoringPermission)
        .filter(
            TailoringPermission.level == level,
            TailoringPermission.change_type == change_type,
        )
        .first()
    )
    return bool(permission and permission.auto_apply)


def set_tailoring_permission(
    session: Session, level: str, change_type: str, auto_apply: bool
) -> TailoringPermission:
    permission = (
        session.query(TailoringPermission)
        .filter(
            TailoringPermission.level == level,
            TailoringPermission.change_type == change_type,
        )
        .first()
    )
    if permission is None:
        permission = TailoringPermission(level=level, change_type=change_type, auto_apply=auto_apply)
        session.add(permission)
    else:
        permission.auto_apply = auto_apply
    session.commit()
    session.refresh(permission)
    return permission