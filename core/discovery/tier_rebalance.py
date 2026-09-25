import datetime
import logging

from sqlalchemy import func

from core.discovery.interval import TIER_INTERVALS, bucket_index_for_age
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)


def rebalance_undated_companies() -> None:
    now = datetime.datetime.utcnow()
    session = DiscoverySessionLocal()
    try:
        dated_companies = (
            session.query(DiscoveredCompany.last_activity_at)
            .filter(
                DiscoveredCompany.active.is_(True),
                DiscoveredCompany.is_deleted.is_(False),
                DiscoveredCompany.has_ever_had_postings.is_(True),
                DiscoveredCompany.last_activity_at.isnot(None),
            )
            .all()
        )

        total_dated = len(dated_companies)
        if total_dated == 0:
            return

        tier_counts = [0] * len(TIER_INTERVALS)
        for (last_activity_at,) in dated_companies:
            tier_counts[bucket_index_for_age(now - last_activity_at)] += 1

        undated_rows = (
            session.query(DiscoveredCompany.id, func.count(DiscoveredJobPosting.id))
            .join(DiscoveredJobPosting, DiscoveredJobPosting.company_id == DiscoveredCompany.id)
            .filter(
                DiscoveredCompany.active.is_(True),
                DiscoveredCompany.is_deleted.is_(False),
                DiscoveredCompany.has_ever_had_postings.is_(True),
                DiscoveredCompany.last_activity_at.is_(None),
            )
            .group_by(DiscoveredCompany.id)
            .order_by(func.count(DiscoveredJobPosting.id).desc())
            .all()
        )

        total_undated = len(undated_rows)
        if total_undated == 0:
            return

        proportions = [count / total_dated for count in tier_counts]

        cursor = 0
        assigned: dict[int, int] = {}
        for tier_index, proportion in enumerate(proportions):
            take = min(round(proportion * total_undated), total_undated - cursor)
            for company_id, _ in undated_rows[cursor : cursor + take]:
                assigned[company_id] = tier_index
            cursor += take

        for company_id, _ in undated_rows[cursor:]:
            assigned[company_id] = len(TIER_INTERVALS) - 1

        for company_id, tier_index in assigned.items():
            session.query(DiscoveredCompany).filter(DiscoveredCompany.id == company_id).update(
                {DiscoveredCompany.assigned_tier: tier_index}, synchronize_session=False
            )
        session.commit()

        logger.info(
            "[tier-rebalance] %s dated companies, %s undated companies rebalanced, tier proportions=%s",
            total_dated, total_undated, proportions,
        )
    finally:
        session.close()