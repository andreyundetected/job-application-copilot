import hashlib
import logging

from core.automation import stages
from core.automation.pipeline import maybe_auto_answer_base_questions, maybe_auto_tailor
from core.db import crud
from core.db.session import SessionLocal
from core.discovery import run_control
from core.discovery.ats import extract_job_text_with_extractor
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal
from core.notifications.telegram import notify_job_evaluated
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


def compute_discovery_key(ats_name: str, url: str) -> str:
    return hashlib.sha256(f"{ats_name}:{url}".encode("utf-8")).hexdigest()


def process_discovered_posting(discovered_posting_id: int) -> bool:
    discovery_session = DiscoverySessionLocal()
    try:
        discovered_posting = discovery_crud.get_discovered_posting(discovery_session, discovered_posting_id)
        if discovered_posting is None:
            return False
        company = discovery_crud.get_company(discovery_session, discovered_posting.company_id)
        if company is None:
            return False
        url = discovered_posting.url
        ats_name = company.ats_name
        already_promoted = discovered_posting.promoted_job_posting_id is not None
    finally:
        discovery_session.close()

    if already_promoted:
        return True

    discovery_key = compute_discovery_key(ats_name, url)

    session = SessionLocal()
    try:
        existing_job = crud.get_job_posting_by_discovery_key(session, discovery_key)
    finally:
        session.close()

    if existing_job is not None:
        link_session = DiscoverySessionLocal()
        try:
            discovery_crud.set_promoted_job_posting(link_session, discovered_posting_id, existing_job.id)
        finally:
            link_session.close()
        logger.info("[discovery] posting %s: already processed as job %s, skipping", discovered_posting_id, existing_job.id)
        return True

    job_text = extract_job_text_with_extractor(ats_name, url)
    if job_text is None:
        logger.warning("[discovery] posting %s: scrape failed (url=%s, ats=%s)", discovered_posting_id, url, ats_name)
        return False

    session = SessionLocal()
    try:
        resume_version = crud.get_active_resume_version(session, "resume")
        if resume_version is None:
            logger.warning("[discovery] posting %s: no active resume, skipping", discovered_posting_id)
            return False

        settings = crud.get_automation_settings(session)
        if settings is None:
            settings = crud.upsert_automation_settings(session)

        resume_text = resume_version.raw_text
        linkedin = crud.get_active_resume_version(session, "linkedin")
        linkedin_text = linkedin.raw_text if linkedin else ""
        blockers = [rule.text for rule in crud.list_blocker_rules(session)]
        scoring_factors = [
            {"id": factor.id, "text": factor.text, "direction": factor.direction, "weight": factor.weight}
            for factor in crud.list_scoring_factors(session)
        ]
        profile = crud.get_candidate_profile(session)
        extra_info = profile.extra_info if profile else None

        job = crud.create_job_posting(
            session, raw_text=job_text, source_url=url, source="discovery", discovery_key=discovery_key
        )
        crud.update_job_pipeline_stage(session, job.id, stages.SCRAPED)
        crud.set_job_activity(session, job.id, "Evaluating fit...")

        link_session = DiscoverySessionLocal()
        try:
            discovery_crud.set_promoted_job_posting(link_session, discovered_posting_id, job.id)
        finally:
            link_session.close()

        provider = get_llm_provider()

        run_control.eval_start()
        try:
            result = evaluate_job_posting(
                provider,
                job_posting_text=job_text,
                resume_text=resume_text,
                linkedin_text=linkedin_text,
                blockers=blockers,
                scoring_factors=scoring_factors,
                extra_info=extra_info,
            )
        except Exception as error:
            run_control.eval_finish(passed=False, archived=False)
            logger.error("[discovery] posting %s: evaluation failed: %s", discovered_posting_id, error)
            crud.set_job_activity(session, job.id, None)
            return False

        crud.update_job_quick_meta(
            session,
            job.id,
            company=result["company"],
            title=result["role"],
            location=result["location"],
            location_country=result["location_country"],
            location_state=result["location_state"],
            location_city=result["location_city"],
            work_mode=result["work_mode"],
        )

        try:
            quick_result = quick_extract_job_posting(provider, job_text)
            crud.update_job_quick_meta(
                session,
                job.id,
                employment_type=quick_result["employment_type"],
                tags=quick_result["tags"],
            )
        except Exception as error:
            logger.warning("[discovery] posting %s: quick-extract failed, leaving unset: %s", discovered_posting_id, error)

        crud.create_evaluation(
            session,
            job_posting_id=job.id,
            resume_version_id=resume_version.id,
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
        crud.ensure_draft_application(session, job.id, source_platform="discovery")

        crud.set_job_activity(session, job.id, None)
        crud.update_job_pipeline_stage(session, job.id, stages.EVALUATED)

        stage = _decide_stage(result["score"], settings.min_score_to_proceed, settings.max_score_to_archive)
        run_control.eval_finish(passed=stage == stages.PASSED, archived=stage == stages.ARCHIVED_AUTO)

        if stage == stages.ARCHIVED_AUTO:
            crud.archive_job_posting(session, job.id)
            crud.update_job_pipeline_stage(session, job.id, stages.ARCHIVED_AUTO)
        elif stage == stages.PASSED:
            crud.update_job_pipeline_stage(session, job.id, stages.PASSED)
            maybe_auto_tailor(session, None, job, job_text, result)
            maybe_auto_answer_base_questions(session, None, job, job_text)
        else:
            crud.update_job_pipeline_stage(session, job.id, stages.NEEDS_REVIEW)

        notify_job_evaluated(company=result["company"], role=result["role"], score=result["score"], job_id=job.id)

        return True
    finally:
        session.close()