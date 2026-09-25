import logging

from core.db import crud
from core.db.session import SessionLocal
from core.discovery.eval_executor import submit_eval_task
from core.discovery.pipeline import process_discovered_posting
from core.discovery.quick_filter import quick_filter_search_results
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal
from core.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_BATCH_SIZE = 25


def _chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _mark_discarded(discovered_posting_id: int) -> None:
    session = DiscoverySessionLocal()
    try:
        posting = session.get(DiscoveredJobPosting, discovered_posting_id)
        if posting is not None:
            posting.discarded_by_quick_screen = True
            session.commit()
    finally:
        session.close()


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

    provider = get_llm_provider()
    passed_count = 0
    skipped_count = 0

    for chunk in _chunked(items, _BATCH_SIZE):
        try:
            verdicts = quick_filter_search_results(provider, chunk, resume_text, linkedin_text, blockers, extra_info)
        except Exception as error:
            logger.error("[quick-screen] batch failed, failing open: %s", error)
            verdicts = {item["id"]: "proceed" for item in chunk}

        for item in chunk:
            if verdicts.get(item["id"], "proceed") == "skip":
                skipped_count += 1
                _mark_discarded(item["id"])
            else:
                passed_count += 1
                submit_eval_task(process_discovered_posting, item["id"])

    logger.info("[quick-screen] %s passed, %s skipped", passed_count, skipped_count)
    return {"passed": passed_count, "skipped": skipped_count}