import logging

from core.automation import stages
from core.automation.pipeline import maybe_auto_answer_base_questions, maybe_auto_tailor
from core.db import crud
from core.db.session import SessionLocal
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting
from core.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


def _decide_stage(score: int | None, min_score_to_proceed: int, max_score_to_archive: int) -> str:
    if score is None:
        return stages.NEEDS_REVIEW
    if score <= max_score_to_archive:
        return stages.ARCHIVED_AUTO
    if score >= min_score_to_proceed:
        return stages.PASSED
    return stages.NEEDS_REVIEW


def retry_stuck_job(job_id: int) -> bool:
    """Re-runs whatever step a job appears to have gotten stuck on (missing
    company/title, or no evaluation yet), using only data already stored on
    the job (raw_text). Called by the watchdog when a job's activity_label
    has been set for too long, almost always because a background thread
    died silently mid-pipeline (unawaited executor future)."""
    session = SessionLocal()
    try:
        job = crud.get_job_posting(session, job_id)
        if job is None:
            return False

        crud.increment_job_retry_count(session, job_id)
        crud.set_job_activity(session, job_id, "Retrying...")

        resume = crud.get_active_resume_version(session, "resume")
        if resume is None:
            crud.set_job_activity(session, job_id, None)
            return False

        provider = get_llm_provider()

        if not job.company or not job.title:
            try:
                quick_result = quick_extract_job_posting(provider, job.raw_text)
                crud.update_job_quick_meta(
                    session,
                    job_id,
                    company=quick_result["company"],
                    title=quick_result["role"],
                    location=quick_result["location"],
                    location_country=quick_result["location_country"],
                    location_state=quick_result["location_state"],
                    location_city=quick_result["location_city"],
                    work_mode=quick_result["work_mode"],
                    employment_type=quick_result["employment_type"],
                    tags=quick_result["tags"],
                )
            except Exception as error:
                logger.warning("[recovery] job %s: quick_extract retry failed: %s", job_id, error)

        existing_evaluations = crud.list_evaluations_for_job(session, job_id)
        if not existing_evaluations:
            linkedin = crud.get_active_resume_version(session, "linkedin")
            blockers = [rule.text for rule in crud.list_blocker_rules(session)]
            scoring_factors = [
                {"id": factor.id, "text": factor.text, "direction": factor.direction, "weight": factor.weight}
                for factor in crud.list_scoring_factors(session)
            ]
            profile = crud.get_candidate_profile(session)

            try:
                result = evaluate_job_posting(
                    provider,
                    job_posting_text=job.raw_text,
                    resume_text=resume.raw_text,
                    linkedin_text=linkedin.raw_text if linkedin else "",
                    blockers=blockers,
                    scoring_factors=scoring_factors,
                    extra_info=profile.extra_info if profile else None,
                )
            except Exception as error:
                logger.error("[recovery] job %s: evaluation retry failed: %s", job_id, error)
                crud.set_job_activity(session, job_id, None)
                return False

            crud.update_job_quick_meta(
                session,
                job_id,
                company=result["company"],
                title=result["role"],
                location=result["location"],
                location_country=result["location_country"],
                location_state=result["location_state"],
                location_city=result["location_city"],
                work_mode=result["work_mode"],
            )
            crud.create_evaluation(
                session,
                job_posting_id=job_id,
                resume_version_id=resume.id,
                verdict=result["verdict"],
                blocker_bullets={"cons": result["cons"]},
                fit_score=result["score"],
                fit_bullets={"pros": result["pros"]},
                checked_keywords={
                    "location": result["location"],
                    "work_mode": result["work_mode"],
                    "salary": result["salary"],
                    "matched_factors": result["matched_factors"],
                    "summary": result["summary"],
                },
            )
            crud.ensure_draft_application(session, job_id, source_platform=job.source or "recovery")
            crud.update_job_pipeline_stage(session, job_id, stages.EVALUATED)

            settings = crud.get_automation_settings(session) or crud.upsert_automation_settings(session)
            stage = _decide_stage(result["score"], settings.min_score_to_proceed, settings.max_score_to_archive)

            if stage == stages.ARCHIVED_AUTO:
                crud.archive_job_posting(session, job_id)
                crud.update_job_pipeline_stage(session, job_id, stages.ARCHIVED_AUTO)
            elif stage == stages.PASSED:
                crud.update_job_pipeline_stage(session, job_id, stages.PASSED)
                maybe_auto_tailor(session, None, job, job.raw_text, result)
                maybe_auto_answer_base_questions(session, None, job, job.raw_text)
            else:
                crud.update_job_pipeline_stage(session, job_id, stages.NEEDS_REVIEW)

        crud.set_job_activity(session, job_id, None)
        crud.reset_job_retry_count(session, job_id)
        return True
    finally:
        session.close()