import datetime
import logging

from core.discovery.quick_screen import quick_screen_and_dispatch
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
                DiscoveredJobPosting.discarded_by_quick_screen.is_(None),
                DiscoveredJobPosting.posted_at.isnot(None),
                DiscoveredJobPosting.posted_at >= cutoff,
            )
            .all()
        )
        posting_ids = [p.id for p in postings]
    finally:
        session.close()

    logger.info("[discovery] backlog pass: %s postings within %sh window", len(posting_ids), hours)
    quick_screen_and_dispatch(posting_ids)
    return len(posting_ids)


def run_catch_up_pass() -> int:
    session = DiscoverySessionLocal()
    try:
        postings = (
            session.query(DiscoveredJobPosting)
            .filter(
                DiscoveredJobPosting.promoted_job_posting_id.is_(None),
                DiscoveredJobPosting.discarded_by_quick_screen.is_(None),
            )
            .all()
        )
        posting_ids = [p.id for p in postings]
    finally:
        session.close()

    logger.info("[discovery] catch-up pass: %s unprocessed postings found", len(posting_ids))
    quick_screen_and_dispatch(posting_ids)
    return len(posting_ids)