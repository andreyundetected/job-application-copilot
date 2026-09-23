import logging
from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery.ats import all_extractors
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)


def _scan_one_extractor(extractor) -> tuple[str, int]:
    slugs = extractor.list_wayback_slugs()
    logger.info("[wayback] %s: found %s slugs on Wayback", extractor.name, len(slugs))

    session = DiscoverySessionLocal()
    try:
        created = discovery_crud.bulk_upsert_companies(session, extractor.name, slugs)
        return extractor.name, created
    finally:
        session.close()


def run_wayback_scan_cycle() -> None:
    extractors = all_extractors()
    logger.info("[wayback] starting scan cycle over %s ATS platforms", len(extractors))

    with ThreadPoolExecutor(max_workers=config.DISCOVERY_WAYBACK_MAX_WORKERS) as executor:
        futures = {executor.submit(_scan_one_extractor, extractor): extractor.name for extractor in extractors}
        for future in futures:
            ats_name = futures[future]
            try:
                name, created = future.result()
                logger.info("[wayback] %s: %s new companies added", name, created)
            except Exception as error:
                logger.error("[wayback] %s: scan failed: %s", ats_name, error)

    session = DiscoverySessionLocal()
    try:
        discovery_crud.mark_wayback_run(session)
    finally:
        session.close()

    logger.info("[wayback] scan cycle done")