import datetime
import logging

from core.discovery.eval_executor import submit_eval_task
from core.discovery.pipeline import process_discovered_posting
from core.discovery_db.models import DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)


def run_backlog_pass(hours: int) -> int:
    if hours <= 0:
        return 0

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

    session = DiscoverySessionLocal()
    try:
        postings = (
            session.query(DiscoveredJobPosting)
            .filter(
                DiscoveredJobPosting.promoted_job_posting_id.is_(None),
                DiscoveredJobPosting.posted_at.isnot(None),
                DiscoveredJobPosting.posted_at >= cutoff,
            )
            .all()
        )
        posting_ids = [p.id for p in postings]
    finally:
        session.close()

    logger.info("[discovery] backlog pass: %s postings within %sh window", len(posting_ids), hours)

    for posting_id in posting_ids:
        submit_eval_task(process_discovered_posting, posting_id)

    return len(posting_ids)