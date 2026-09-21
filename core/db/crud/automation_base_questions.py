from sqlalchemy.orm import Session

from core.db.models import AutomationBaseQuestion


def create_automation_base_question(session: Session, question_text: str) -> AutomationBaseQuestion:
    existing = list_automation_base_questions(session)
    row = AutomationBaseQuestion(question_text=question_text, order=len(existing))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_automation_base_questions(session: Session) -> list[AutomationBaseQuestion]:
    return session.query(AutomationBaseQuestion).order_by(AutomationBaseQuestion.order.asc()).all()


def delete_automation_base_question(session: Session, question_id: int) -> bool:
    row = session.get(AutomationBaseQuestion, question_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True