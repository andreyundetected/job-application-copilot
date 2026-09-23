import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery.ats import all_extractors
from core.discovery.interval import compute_next_check_at
from core.discovery.pipeline import process_discovered_posting
from core.discovery.rate_limiter import throttle
from core.discovery.eval_executor import submit_eval_task
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

_EXTRACTORS_BY_NAME = {extractor.name: extractor for extractor in all_extractors()}


def _check_one_company(company_id: int, ats_name: str, slug: str) -> None:
    session = DiscoverySessionLocal()
    try:
        extractor = _EXTRACTORS_BY_NAME.get(ats_name)
        if extractor is None:
            logger.warning("[poll] no extractor registered for ats_name=%s (company_id=%s)", ats_name, company_id)
            return

        now = datetime.datetime.utcnow()
        failed = False
        had_new_activity = False

        try:
            throttle(ats_name)
            postings = extractor.list_active_postings(slug)
        except Exception as error:
            logger.warning("[poll] %s/%s: list_active_postings failed: %s", ats_name, slug, error)
            failed = True
            postings = []

        if postings:
            existing_ids = discovery_crud.get_existing_external_ids(session, company_id)
            new_postings = [p for p in postings if p["external_id"] not in existing_ids]

            for posting in new_postings:
                created = discovery_crud.create_discovered_posting(session, company_id, posting)
                had_new_activity = True
                submit_eval_task(process_discovered_posting, created.id)

            if new_postings:
                logger.info("[poll] %s/%s: %s new postings found", ats_name, slug, len(new_postings))

        company = discovery_crud.get_company(session, company_id)
        last_activity_at = company.last_activity_at if company else None
        if had_new_activity:
            last_activity_at = now

        next_check_at = compute_next_check_at(last_activity_at, now)
        discovery_crud.mark_company_checked(
            session, company_id, next_check_at=next_check_at, had_new_activity=had_new_activity, failed=failed
        )
    finally:
        session.close()


def run_poll_tick() -> None:
    session = DiscoverySessionLocal()
    try:
        now = datetime.datetime.utcnow()
        due_companies = discovery_crud.list_due_companies(session, now, config.DISCOVERY_POLL_BATCH_SIZE)
        batch = [(c.id, c.ats_name, c.slug) for c in due_companies]
    finally:
        session.close()

    if not batch:
        return

    logger.info("[poll] tick: checking %s due companies", len(batch))

    with ThreadPoolExecutor(max_workers=config.DISCOVERY_POLL_MAX_WORKERS) as executor:
        futures = [executor.submit(_check_one_company, *item) for item in batch]
        for future in futures:
            try:
                future.result()
            except Exception as error:
                logger.error("[poll] company check raised unexpectedly: %s", error)