import logging
from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery import run_control
from core.discovery.ats import all_extractors
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)


def _scan_one_extractor(extractor) -> tuple[str, int]:
    if run_control.is_cancelled():
        return extractor.name, 0

    logger.info("[wayback] %s: querying CDX for domains %s", extractor.name, extractor.site_filter_domains)
    slugs = extractor.list_wayback_slugs(is_cancelled=run_control.is_cancelled)
    logger.info("[wayback] %s: found %s slugs on Wayback", extractor.name, len(slugs))

    session = DiscoverySessionLocal()
    try:
        created = discovery_crud.bulk_upsert_companies(session, extractor.name, slugs)
        return extractor.name, created
    finally:
        session.close()


def run_wayback_scan_cycle() -> None:
    extractors = all_extractors()
    run_control.set_phase("wayback")
    logger.info("[wayback] starting scan cycle over %s ATS platforms", len(extractors))
    run_control.set_wayback_total(len(extractors))

    with ThreadPoolExecutor(max_workers=config.DISCOVERY_WAYBACK_MAX_WORKERS) as executor:
        futures = {executor.submit(_scan_one_extractor, extractor): extractor.name for extractor in extractors}
        for future in futures:
            ats_name = futures[future]
            try:
                name, created = future.result()
                run_control.add_new_companies(created)
                run_control.increment_wayback_done()
                logger.info("[wayback] %s: %s new companies added", name, created)
            except Exception as error:
                run_control.increment_wayback_done()
                logger.error("[wayback] %s: scan failed: %s", ats_name, error)

    session = DiscoverySessionLocal()
    try:
        discovery_crud.mark_wayback_run(session)
    finally:
        session.close()

    logger.info("[wayback] scan cycle done")