from sqlalchemy.orm import Session

from core.db.models import TailoringPermission


def list_tailoring_permissions(session: Session) -> list[TailoringPermission]:
    return session.query(TailoringPermission).all()


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