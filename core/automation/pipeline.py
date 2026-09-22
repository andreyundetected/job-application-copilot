import logging
from concurrent.futures import as_completed

from sqlalchemy.orm import Session

import config

logger = logging.getLogger(__name__)
from core.automation import stages
from core.automation.executor import submit_automation_task
from core.db import crud
from core.db.session import SessionLocal
from core.discovery.ats import detect_platform, extract_job_text
from core.discovery.quick_filter import quick_filter_search_results
from core.discovery.search_provider import SerpentSearchError, get_search_provider
from core.discovery.url_utils import normalize_url
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting
from core.providers.factory import get_llm_provider
from core.questions.pipeline import (
    classify_template_category,
    generate_cover_letter_answers,
    generate_general_answers_initial,
    generate_summary_answers,
)
from core.tailoring.fragment_pipeline import (
    propose_medium_fragment_changes,
    propose_soft_fragment_changes,
)
from core.tailoring.html_diff import apply_fragment


def run_automation_pipeline_task(run_id: int) -> dict:
    session = SessionLocal()
    try:
        run_automation_pipeline(session, run_id)
        return {"run_id": run_id}
    finally:
        session.close()


def run_automation_pipeline(session: Session, run_id: int) -> None:
    run = crud.get_automation_run(session, run_id)
    if run is None:
        return

    settings = crud.get_automation_settings(session)
    if settings is None:
        settings = crud.upsert_automation_settings(session)

    crud.mark_run_started(session, run_id)

    try:
        _run_search_and_process(session, run, settings)
        crud.mark_run_finished(session, run_id, status="done")
    except Exception as error:
        crud.mark_run_failed(session, run_id, error=str(error))
        raise


def _run_search_and_process(session: Session, run, settings) -> None:
    queries = list(run.queries_planned or [])
    if run.max_queries_override:
        queries = queries[: run.max_queries_override]

    is_capped = run.max_results_override is not None

    resume = crud.get_active_resume_version(session, "resume")
    linkedin = crud.get_active_resume_version(session, "linkedin")
    resume_text = resume.raw_text if resume else ""
    linkedin_text = linkedin.raw_text if linkedin else ""
    blockers = [rule.text for rule in crud.list_blocker_rules(session)]
    scoring_factors = [
        {"id": factor.id, "text": factor.text, "direction": factor.direction, "weight": factor.weight}
        for factor in crud.list_scoring_factors(session)
    ]
    profile = crud.get_candidate_profile(session)
    extra_info = profile.extra_info if profile else None

    for query_text in queries:
        if is_capped and crud.count_promoted_for_run(session, run.id) >= run.max_results_override:
            break

        candidate_results = _run_single_query(session, run, query_text, settings)

        if settings.quick_filter_enabled and candidate_results:
            candidate_results = _apply_quick_filter(
                session, run, candidate_results, resume_text, linkedin_text, blockers, extra_info
            )

        if is_capped:
            for search_result in candidate_results:
                if crud.count_promoted_for_run(session, run.id) >= run.max_results_override:
                    break
                _process_search_result(
                    session,
                    run.id,
                    search_result["id"],
                    resume_text,
                    linkedin_text,
                    blockers,
                    scoring_factors,
                    extra_info,
                )
        else:
            _process_results_in_parallel(
                run.id, candidate_results, resume_text, linkedin_text, blockers, scoring_factors, extra_info
            )


def _run_single_query(session: Session, run, query_text: str, settings) -> list[dict]:
    provider = get_search_provider()

    logger.info("[run %s] searching: %r", run.id, query_text)

    try:
        search_response = provider.search(
            query_text, num=settings.serpent_num_per_query, date=settings.default_time_range
        )
    except SerpentSearchError as error:
        logger.error("[run %s] search failed for %r: %s", run.id, query_text, error)
        crud.append_run_warning(session, run.id, f"Search failed for '{query_text}': {error}")
        return []

    crud.create_usage_log(
        session,
        provider="serpent",
        operation="search_query",
        automation_run_id=run.id,
        requested_num=search_response["requested_num"],
        returned_count=search_response["returned_count"],
        raw_usage=search_response["raw_response"],
    )

    if search_response["returned_count"] == 0:
        logger.warning("[run %s] 0 results for query: %r", run.id, query_text)
        crud.append_run_warning(session, run.id, f"0 search results for query: '{query_text}'")

    payload = [
        {
            "query_text": query_text,
            "url": item["url"],
            "url_normalized": normalize_url(item["url"]),
            "source_platform": detect_platform(item["url"]),
            "title": item.get("title"),
            "snippet": item.get("snippet"),
        }
        for item in search_response["results"]
    ]

    created, dedup_stats = crud.bulk_create_search_results(session, run.id, payload)
    logger.info(
        "[run %s] query %r: %s parsed / %s created / %s already-known-from-past-runs / %s intra-batch-dupes",
        run.id,
        query_text,
        len(search_response["results"]),
        len(created),
        dedup_stats["skipped_already_known"],
        dedup_stats["skipped_intra_batch"],
    )
    if dedup_stats["skipped_already_known"] > 0 and not created:
        crud.append_run_warning(
            session,
            run.id,
            f"All {dedup_stats['skipped_already_known']} results for '{query_text}' were already scraped in a previous run",
        )
    crud.increment_run_counters(session, run.id, found_count=len(created))

    return [{"id": row.id, "title": row.title, "snippet": row.snippet, "url": row.url} for row in created]


def _apply_quick_filter(
    session: Session,
    run,
    search_results: list[dict],
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    extra_info: str | None,
) -> list[dict]:
    provider = get_llm_provider()

    try:
        verdicts = quick_filter_search_results(
            provider, search_results, resume_text, linkedin_text, blockers, extra_info
        )
        _log_llm_usage(session, provider, run.id, "quick_filter")
    except Exception as error:
        logger.error(
            "[run %s] quick filter LLM call failed (provider=%s): %s - failing open, all %s results proceed",
            run.id, config.LLM_PROVIDER, error, len(search_results),
        )
        crud.append_run_warning(
            session, run.id, f"Quick filter LLM call failed ({error}); all results proceeded unfiltered"
        )
        return search_results

    proceeding = []
    for result in search_results:
        verdict = verdicts.get(result["id"], "proceed")
        crud.set_quick_filter_verdict(session, result["id"], verdict)
        if verdict == "proceed":
            proceeding.append(result)

    logger.info(
        "[run %s] quick filter: %s in / %s proceeding",
        run.id,
        len(search_results),
        len(proceeding),
    )
    if search_results and not proceeding:
        crud.append_run_warning(
            session, run.id, f"Quick filter skipped all {len(search_results)} results this batch"
        )

    crud.increment_run_counters(session, run.id, quick_filtered_count=len(search_results))
    return proceeding


def _process_search_result(
    session: Session,
    run_id: int,
    search_result_id: int,
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    scoring_factors: list[dict],
    extra_info: str | None,
) -> bool:
    try:
        search_result = crud.get_search_result(session, search_result_id)
        if search_result is None:
            return False

        resume_version = crud.get_active_resume_version(session, "resume")
        if resume_version is None:
            return False

        settings = crud.get_automation_settings(session)
        if settings is None:
            settings = crud.upsert_automation_settings(session)

        job_text = extract_job_text(search_result.url)
        if job_text is None:
            logger.warning(
                "[run %s] job scrape failed for search_result %s (url=%s), see extract_job_text logs above",
                run_id, search_result_id, search_result.url,
            )
            return False

        job = crud.create_job_posting(
            session, raw_text=job_text, source_url=search_result.url, source="automation"
        )
        crud.update_job_pipeline_stage(session, job.id, stages.SCRAPED)
        crud.set_promoted_job_posting(session, search_result_id, job.id)
        crud.increment_run_counters(session, run_id, scraped_count=1)
        crud.set_job_activity(session, job.id, "Evaluating fit...")

        provider = get_llm_provider()
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
            logger.error(
                "[run %s] evaluation LLM call failed for job %s (provider=%s): %s",
                run_id, job.id, config.LLM_PROVIDER, error,
            )
            crud.append_run_warning(
                session, run_id, f"Evaluation failed for job {job.id} ({job.source_url}): {error}"
            )
            crud.set_job_activity(session, job.id, None)
            return False
        _log_llm_usage(session, provider, run_id, "evaluation", job_posting_id=job.id)

        crud.update_job_quick_meta(
            session,
            job.id,
            company=result["company"],
            title=result["role"],
            location=result["location"],
            work_mode=result["work_mode"],
        )

        try:
            quick_result = quick_extract_job_posting(provider, job_text)
            _log_llm_usage(session, provider, run_id, "quick_extract", job_posting_id=job.id)
            crud.update_job_quick_meta(
                session,
                job.id,
                employment_type=quick_result["employment_type"],
                tags=quick_result["tags"],
            )
        except Exception as error:
            logger.warning(
                "[run %s] job %s: tag/employment_type quick-extract failed, leaving unset: %s",
                run_id, job.id, error,
            )

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

        crud.set_job_activity(session, job.id, None)
        crud.update_job_pipeline_stage(session, job.id, stages.EVALUATED)
        crud.increment_run_counters(session, run_id, evaluated_count=1)

        stage = _decide_stage(result["score"], settings.min_score_to_proceed, settings.max_score_to_archive)

        if stage == stages.ARCHIVED_AUTO:
            if settings.auto_archive_enabled:
                crud.archive_job_posting(session, job.id)
            crud.update_job_pipeline_stage(session, job.id, stages.ARCHIVED_AUTO)
            crud.increment_run_counters(session, run_id, archived_count=1)
        elif stage == stages.PASSED:
            crud.update_job_pipeline_stage(session, job.id, stages.PASSED)
            crud.increment_run_counters(session, run_id, passed_count=1)
            maybe_auto_tailor(session, run_id, job, job_text, result)
            maybe_auto_answer_base_questions(session, run_id, job, job_text)
        else:
            crud.update_job_pipeline_stage(session, job.id, stages.NEEDS_REVIEW)

        return True
    except Exception as error:
        crud.append_run_warning(
            session, run_id, f"Failed to process search_result {search_result_id}: {error}"
        )
        return False


def _process_search_result_task(
    run_id: int,
    search_result_id: int,
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    scoring_factors: list[dict],
    extra_info: str | None,
) -> bool:
    session = SessionLocal()
    try:
        return _process_search_result(
            session, run_id, search_result_id, resume_text, linkedin_text, blockers, scoring_factors, extra_info
        )
    finally:
        session.close()


def _process_results_in_parallel(
    run_id: int,
    search_results: list[dict],
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    scoring_factors: list[dict],
    extra_info: str | None,
) -> None:
    futures = [
        submit_automation_task(
            _process_search_result_task,
            run_id,
            result["id"],
            resume_text,
            linkedin_text,
            blockers,
            scoring_factors,
            extra_info,
        )
        for result in search_results
    ]
    for future in as_completed(futures):
        future.result()


def _decide_stage(score: int | None, min_score_to_proceed: int, max_score_to_archive: int) -> str:
    if score is None:
        return stages.NEEDS_REVIEW
    if score <= max_score_to_archive:
        return stages.ARCHIVED_AUTO
    if score >= min_score_to_proceed:
        return stages.PASSED
    return stages.NEEDS_REVIEW


def maybe_auto_tailor(
    session: Session,
    run_id: int | None,
    job,
    job_text: str,
    eval_result: dict,
    level_has_auto_apply=crud.level_has_auto_apply,
    is_auto_apply=crud.is_auto_apply,
) -> None:
    # There's no separate "run soft/medium" toggle anymore - whether a level runs
    # at all is derived straight from the auto-apply matrix: if nothing in a level
    # is checked, there's no point spending an LLM call proposing changes for it.
    # level_has_auto_apply/is_auto_apply are injectable so this same function
    # drives both the Automation pipeline's permission table and the Evaluator
    # sidebar's independent "manual assist" permission table.
    soft_active = level_has_auto_apply(session, "soft")
    medium_active = level_has_auto_apply(session, "medium")

    if not soft_active and not medium_active:
        logger.info(
            "[run %s] job %s: no auto-apply tailoring permissions enabled, skipping", run_id, job.id
        )
        return

    crud.set_job_activity(session, job.id, "Tailoring resume...")

    crud.set_job_activity(session, job.id, "Tailoring resume...")

    resume = crud.get_active_resume_version(session, "resume")
    if resume is None or not resume.content_html:
        logger.warning(
            "[run %s] job %s: auto-tailoring skipped - no active resume with content_html", run_id, job.id
        )
        if run_id is not None:
            crud.append_run_warning(session, run_id, "Auto-tailor skipped: no active resume HTML set")
        crud.set_job_activity(session, job.id, None)
        return

    tailoring_session = crud.get_tailoring_session_for_job(session, job.id)
    if tailoring_session is None:
        tailoring_session = crud.create_tailoring_session(
            session,
            job_posting_id=job.id,
            resume_version_id=resume.id,
            working_content={},
            working_html=resume.content_html,
        )

    matched_factors = eval_result.get("matched_factors") or []
    provider = get_llm_provider()

    if soft_active:
        soft_changes = propose_soft_fragment_changes(
            provider,
            job_posting_text=job_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            keywords=[],
        )
        _log_llm_usage(session, provider, run_id, "tailoring_soft", job_posting_id=job.id)
        tailoring_session = _apply_auto_tailoring_changes(
            session, tailoring_session, soft_changes, "soft", is_auto_apply
        )

    if medium_active:
        medium_changes = propose_medium_fragment_changes(
            provider,
            job_posting_text=job_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            keywords=[],
        )
        _log_llm_usage(session, provider, run_id, "tailoring_medium", job_posting_id=job.id)
        tailoring_session = _apply_auto_tailoring_changes(
            session, tailoring_session, medium_changes, "medium", is_auto_apply
        )

    crud.update_job_pipeline_stage(session, job.id, stages.TAILORED)


def maybe_auto_answer_base_questions(
    session: Session,
    run_id: int | None,
    job,
    job_text: str,
    list_base_questions=crud.list_automation_base_questions,
) -> None:
    # No separate enabled toggle - having at least one base question configured
    # is itself the signal that this step should run. list_base_questions is
    # injectable for the same reason as above - Automation and the Evaluator's
    # "manual assist" keep fully independent question lists.
    base_questions = list_base_questions(session)
    if not base_questions:
        logger.info("[run %s] job %s: no automation base questions configured, skipping", run_id, job.id)
        return

    crud.set_job_activity(session, job.id, "Answering application questions...")

    existing_applications = [a for a in crud.list_applications(session) if a.job_posting_id == job.id]
    application = existing_applications[0] if existing_applications else crud.create_application(
        session, job_posting_id=job.id, source_platform="automation"
    )

    already_asked = {q.question_text for q in crud.list_form_questions_for_application(session, application.id)}
    to_create = [
        {"question_text": bq.question_text, "answer_type": "document", "category": None, "char_limit": None}
        for bq in base_questions
        if bq.question_text not in already_asked
    ]
    if not to_create:
        logger.info("[run %s] job %s: all base questions already asked on application %s", run_id, job.id, application.id)
        crud.set_job_activity(session, job.id, None)
        return

    provider = get_llm_provider()
    for item in to_create:
        item["category"] = classify_template_category(provider, item["question_text"])

    existing_count = len(crud.list_form_questions_for_application(session, application.id))
    created = crud.bulk_create_form_questions(session, application.id, to_create, order_offset=existing_count)

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

    resume_text = resume.raw_text if resume else ""
    linkedin_text = linkedin.raw_text if linkedin else ""
    extra_info = profile.extra_info if profile else None

    by_category: dict[str, list] = {"cover_letter": [], "summary": [], "general": []}
    for question in created:
        by_category.setdefault(question.category or "general", []).append(question)

    for category, questions_in_category in by_category.items():
        if not questions_in_category:
            continue

        payload = [
            {"id": q.id, "question_text": q.question_text, "char_limit": q.char_limit}
            for q in questions_in_category
        ]

        if category == "cover_letter":
            answers = generate_cover_letter_answers(
                provider, payload, job_posting_text=job_text, resume_text=resume_text,
                linkedin_text=linkedin_text, extra_info=extra_info, links=links,
            )
        elif category == "summary":
            answers = generate_summary_answers(
                provider, payload, job_posting_text=job_text, resume_text=resume_text,
                linkedin_text=linkedin_text, extra_info=extra_info, links=links,
            )
        else:
            answers = generate_general_answers_initial(
                provider, payload, job_posting_text=job_text, resume_text=resume_text,
                linkedin_text=linkedin_text, extra_info=extra_info, links=links,
            )

        for question in questions_in_category:
            result = answers.get(question.id)
            if result is None:
                continue
            crud.set_question_generation_result(
                session, question.id,
                answer_text=result["answer_text"],
                selected_option=None,
                needs_manual_input=result["needs_manual_input"],
                flag_reason=result["flag_reason"],
            )

    crud.set_job_activity(session, job.id, None)
    logger.info(
        "[run %s] job %s: auto-answered %s base questions on application %s",
        run_id, job.id, len(created), application.id,
    )


def _apply_auto_tailoring_changes(
    session: Session, tailoring_session, changes: list[dict], level: str, is_auto_apply=crud.is_auto_apply
):
    if not changes:
        return tailoring_session

    message = crud.create_tailoring_message(
        session, tailoring_session.id, role="assistant", text=f"Auto-{level} tailoring pass."
    )
    created = crud.bulk_create_session_changes(session, tailoring_session.id, message.id, changes)

    for change in created:
        if not is_auto_apply(session, level, change.change_type):
            continue
        try:
            new_html = apply_fragment(
                tailoring_session.working_html or "", change.original_text, change.proposed_text
            )
        except ValueError:
            crud.resolve_tailoring_change(session, change.id, status="failed")
            continue

        tailoring_session = crud.update_working_html(session, tailoring_session.id, new_html)
        crud.resolve_tailoring_change(session, change.id, status="approved")

    return tailoring_session


def _log_llm_usage(
    session: Session,
    provider,
    run_id: int,
    operation: str,
    job_posting_id: int | None = None,
    search_result_id: int | None = None,
) -> None:
    usage = getattr(provider, "last_usage", None) or {}
    crud.create_usage_log(
        session,
        provider=config.LLM_PROVIDER,
        operation=operation,
        automation_run_id=run_id,
        job_posting_id=job_posting_id,
        search_result_id=search_result_id,
        model=usage.get("model"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        reasoning_tokens=usage.get("reasoning_tokens"),
        total_tokens=usage.get("total_tokens"),
    )