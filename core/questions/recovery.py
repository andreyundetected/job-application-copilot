import logging

from core.db import crud
from core.db.session import SessionLocal
from core.providers.factory import get_llm_provider
from core.questions.pipeline import (
    generate_cover_letter_answers,
    generate_general_answers_initial,
    generate_summary_answers,
)

logger = logging.getLogger(__name__)


def retry_stuck_question(question_id: int) -> bool:
    """Re-generates the answer for one form question, same as if the initial
    background task had completed normally. Called by the watchdog when a
    question's pending_task_id has been set for too long."""
    session = SessionLocal()
    try:
        question = crud.get_form_question(session, question_id)
        if question is None:
            return False

        crud.increment_question_retry_count(session, question_id)

        application = crud.get_application(session, question.application_id)
        job = crud.get_job_posting(session, application.job_posting_id) if application else None
        if job is None:
            crud.set_question_pending_task(session, question_id, None)
            return False

        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)

        links = []
        if profile:
            if profile.github_url:
                links.append(profile.github_url)
            if profile.linkedin_url:
                links.append(profile.linkedin_url)
            links.extend(profile.extra_links or [])

        payload = [
            {
                "id": question.id,
                "question_text": question.question_text,
                "char_limit": question.char_limit,
                "template_instructions": question.template_instructions,
            }
        ]
        common_kwargs = dict(
            job_posting_text=job.raw_text,
            resume_text=resume.raw_text if resume else "",
            linkedin_text=linkedin.raw_text if linkedin else "",
            extra_info=profile.extra_info if profile else None,
            writing_preferences=profile.writing_preferences if profile else None,
            links=links,
        )

        provider = get_llm_provider()

        try:
            if question.category == "cover_letter":
                answers = generate_cover_letter_answers(provider, payload, **common_kwargs)
            elif question.category == "summary":
                answers = generate_summary_answers(provider, payload, **common_kwargs)
            else:
                answers = generate_general_answers_initial(provider, payload, **common_kwargs)
        except Exception as error:
            logger.error("[recovery] question %s: retry failed: %s", question_id, error)
            crud.set_question_pending_task(session, question_id, None)
            return False

        result = answers.get(question.id)
        if result is None:
            crud.set_question_pending_task(session, question_id, None)
            return False

        crud.set_question_generation_result(
            session,
            question_id,
            answer_text=result["answer_text"],
            selected_option=None,
            needs_manual_input=result["needs_manual_input"],
            flag_reason=result["flag_reason"],
        )
        crud.set_question_pending_task(session, question_id, None)
        crud.reset_question_retry_count(session, question_id)
        return True
    finally:
        session.close()