from sqlalchemy.orm import Session

from core.db.models import QuestionTemplate


def create_question_template(
    session: Session, label: str, trigger_phrases: list[str], instructions: str
) -> QuestionTemplate:
    existing = list_question_templates(session)
    template = QuestionTemplate(
        label=label,
        trigger_phrases=trigger_phrases,
        instructions=instructions,
        order=len(existing),
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def list_question_templates(session: Session) -> list[QuestionTemplate]:
    return session.query(QuestionTemplate).order_by(QuestionTemplate.order.asc()).all()


def get_question_template(session: Session, template_id: int) -> QuestionTemplate | None:
    return session.get(QuestionTemplate, template_id)


def delete_question_template(session: Session, template_id: int) -> bool:
    template = session.get(QuestionTemplate, template_id)
    if template is None:
        return False
    session.delete(template)
    session.commit()
    return True


def match_question_template(
    templates: list[QuestionTemplate], question_text: str
) -> QuestionTemplate | None:
    lowered = question_text.lower()
    for template in templates:
        for phrase in template.trigger_phrases or []:
            if phrase.strip() and phrase.strip().lower() in lowered:
                return template
    return None