from sqlalchemy.orm import Session

from core.db.models import ManualAssistBaseQuestion, ManualAssistTailoringPermission


def list_manual_assist_tailoring_permissions(session: Session) -> list[ManualAssistTailoringPermission]:
    return session.query(ManualAssistTailoringPermission).all()


def manual_assist_level_has_auto_apply(session: Session, level: str) -> bool:
    return (
        session.query(ManualAssistTailoringPermission)
        .filter(
            ManualAssistTailoringPermission.level == level,
            ManualAssistTailoringPermission.auto_apply.is_(True),
        )
        .first()
        is not None
    )


def manual_assist_is_auto_apply(session: Session, level: str, change_type: str) -> bool:
    permission = (
        session.query(ManualAssistTailoringPermission)
        .filter(
            ManualAssistTailoringPermission.level == level,
            ManualAssistTailoringPermission.change_type == change_type,
        )
        .first()
    )
    return bool(permission and permission.auto_apply)


def set_manual_assist_tailoring_permission(
    session: Session, level: str, change_type: str, auto_apply: bool
) -> ManualAssistTailoringPermission:
    permission = (
        session.query(ManualAssistTailoringPermission)
        .filter(
            ManualAssistTailoringPermission.level == level,
            ManualAssistTailoringPermission.change_type == change_type,
        )
        .first()
    )
    if permission is None:
        permission = ManualAssistTailoringPermission(level=level, change_type=change_type, auto_apply=auto_apply)
        session.add(permission)
    else:
        permission.auto_apply = auto_apply
    session.commit()
    session.refresh(permission)
    return permission


def create_manual_assist_base_question(session: Session, question_text: str) -> ManualAssistBaseQuestion:
    existing = list_manual_assist_base_questions(session)
    row = ManualAssistBaseQuestion(question_text=question_text, order=len(existing))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_manual_assist_base_questions(session: Session) -> list[ManualAssistBaseQuestion]:
    return session.query(ManualAssistBaseQuestion).order_by(ManualAssistBaseQuestion.order.asc()).all()


def delete_manual_assist_base_question(session: Session, question_id: int) -> bool:
    row = session.get(ManualAssistBaseQuestion, question_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True