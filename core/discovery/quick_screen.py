import logging
from concurrent.futures import ThreadPoolExecutor

import config
from core.db import crud
from core.db.session import SessionLocal
from core.discovery import run_control
from core.discovery.eval_executor import submit_eval_task
from core.discovery.pipeline import process_discovered_posting
from core.discovery.quick_filter import quick_filter_search_results
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal
from core.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


def _chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _mark_discarded(discovered_posting_ids: list[int]) -> None:
    if not discovered_posting_ids:
        return
    session = DiscoverySessionLocal()
    try:
        session.query(DiscoveredJobPosting).filter(DiscoveredJobPosting.id.in_(discovered_posting_ids)).update(
            {DiscoveredJobPosting.discarded_by_quick_screen: True}, synchronize_session=False
        )
        session.commit()
    finally:
        session.close()


def _screen_chunk(chunk, resume_text, linkedin_text, blockers, extra_info) -> tuple[int, int]:
    size = len(chunk)
    run_control.flow_add("screen", "active", size)
    try:
        try:
            verdicts = quick_filter_search_results(
                get_llm_provider(), chunk, resume_text, linkedin_text, blockers, extra_info
            )
        except Exception as error:
            logger.error("[quick-screen] batch failed, failing open: %s", error)
            verdicts = {item["id"]: "proceed" for item in chunk}

        skipped_ids = [item["id"] for item in chunk if verdicts.get(item["id"], "proceed") == "skip"]
        skipped_set = set(skipped_ids)
        passed_ids = [item["id"] for item in chunk if item["id"] not in skipped_set]

        _mark_discarded(skipped_ids)
        for posting_id in passed_ids:
            submit_eval_task(process_discovered_posting, posting_id)

        run_control.flow_add("screen", "done", size)
        run_control.flow_add("screen", "passed", len(passed_ids))
        run_control.flow_add("screen", "skipped", len(skipped_ids))
        return len(passed_ids), len(skipped_ids)
    finally:
        run_control.flow_add("screen", "active", -size)


def quick_screen_and_dispatch(discovered_posting_ids: list[int]) -> dict:
    if not discovered_posting_ids:
        return {"passed": 0, "skipped": 0}

    main_session = SessionLocal()
    try:
        resume = crud.get_active_resume_version(main_session, "resume")
        if resume is None:
            for posting_id in discovered_posting_ids:
                submit_eval_task(process_discovered_posting, posting_id)
            return {"passed": len(discovered_posting_ids), "skipped": 0}

        linkedin = crud.get_active_resume_version(main_session, "linkedin")
        blockers = [rule.text for rule in crud.list_blocker_rules(main_session)]
        profile = crud.get_candidate_profile(main_session)
        resume_text = resume.raw_text
        linkedin_text = linkedin.raw_text if linkedin else ""
        extra_info = profile.extra_info if profile else None
    finally:
        main_session.close()

    discovery_session = DiscoverySessionLocal()
    try:
        rows = (
            discovery_session.query(DiscoveredJobPosting, DiscoveredCompany)
            .join(DiscoveredCompany, DiscoveredJobPosting.company_id == DiscoveredCompany.id)
            .filter(DiscoveredJobPosting.id.in_(discovered_posting_ids))
            .all()
        )
    finally:
        discovery_session.close()

    items = []
    for posting, company in rows:
        label = posting.title or f"{company.ats_name}:{posting.external_id}"
        items.append({"id": posting.id, "title": label, "snippet": company.slug, "url": posting.url})

    chunks = list(_chunked(items, max(1, config.DISCOVERY_SCREEN_CHUNK_SIZE)))
    if not chunks:
        return {"passed": 0, "skipped": 0}

    workers = max(1, min(config.DISCOVERY_SCREEN_WORKERS, len(chunks)))
    passed_count = 0
    skipped_count = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="quick-screen") as pool:
        futures = [
            pool.submit(_screen_chunk, chunk, resume_text, linkedin_text, blockers, extra_info) for chunk in chunks
        ]
        for future in futures:
            chunk_passed, chunk_skipped = future.result()
            passed_count += chunk_passed
            skipped_count += chunk_skipped

    logger.info("[quick-screen] %s passed, %s skipped (%s chunks, %s workers)", passed_count, skipped_count, len(chunks), workers)
    return {"passed": passed_count, "skipped": skipped_count}