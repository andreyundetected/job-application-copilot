import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting, DiscoverySettings


def get_or_create_settings(session: Session) -> DiscoverySettings:
    settings = session.query(DiscoverySettings).first()
    if settings is None:
        settings = DiscoverySettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


_RESETTABLE_KEYS = {"last_wayback_run_at", "initial_collection_done_at"}


def update_settings(session: Session, **kwargs) -> DiscoverySettings:
    settings = get_or_create_settings(session)
    for key, value in kwargs.items():
        if not hasattr(settings, key):
            continue
        if value is not None or key in _RESETTABLE_KEYS:
            setattr(settings, key, value)
    session.commit()
    session.refresh(settings)
    return settings


def mark_wayback_run(session: Session) -> None:
    settings = get_or_create_settings(session)
    settings.last_wayback_run_at = datetime.datetime.utcnow()
    session.commit()


def bulk_upsert_companies(session: Session, ats_name: str, slugs: list[str]) -> int:
    """Inserts only slugs not already known for this ATS - never touches an
    existing company's next_check_at/last_activity_at, since that would reset
    its adaptive polling schedule."""
    existing = {
        row[0]
        for row in session.query(DiscoveredCompany.slug).filter(DiscoveredCompany.ats_name == ats_name).all()
    }
    now = datetime.datetime.utcnow()
    created = 0
    for slug in slugs:
        if slug in existing:
            continue
        session.add(
            DiscoveredCompany(
                ats_name=ats_name,
                slug=slug,
                active=True,
                first_seen_at=now,
                last_activity_at=now,
                next_check_at=now,
            )
        )
        existing.add(slug)
        created += 1
    session.commit()
    return created


def list_unchecked_companies_balanced(session: Session, limit: int, ats_names: list[str]) -> list[DiscoveredCompany]:
    if not ats_names:
        return []
    per_domain = max(1, limit // len(ats_names))
    result: list[DiscoveredCompany] = []
    for ats_name in ats_names:
        rows = (
            session.query(DiscoveredCompany)
            .filter(
                DiscoveredCompany.active.is_(True),
                DiscoveredCompany.is_deleted.is_(False),
                DiscoveredCompany.last_checked_at.is_(None),
                DiscoveredCompany.ats_name == ats_name,
            )
            .order_by(DiscoveredCompany.id.asc())
            .limit(per_domain)
            .all()
        )
        result.extend(rows)
    return result[:limit]


def count_unchecked_companies(session: Session) -> int:
    return (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.last_checked_at.is_(None),
        )
        .count()
    )


def list_due_companies_prioritized_balanced(
    session: Session, now: datetime.datetime, limit: int, ats_names: list[str]
) -> list[DiscoveredCompany]:
    if not ats_names:
        return []
    per_domain = max(1, limit // len(ats_names))
    result: list[DiscoveredCompany] = []
    for ats_name in ats_names:
        rows = (
            session.query(DiscoveredCompany)
            .filter(
                DiscoveredCompany.active.is_(True),
                DiscoveredCompany.is_deleted.is_(False),
                DiscoveredCompany.last_checked_at.isnot(None),
                DiscoveredCompany.has_ever_had_postings.is_(True),
                DiscoveredCompany.next_check_at <= now,
                DiscoveredCompany.ats_name == ats_name,
            )
            .order_by(DiscoveredCompany.next_check_at.asc())
            .limit(per_domain)
            .all()
        )
        result.extend(rows)
    return result[:limit]


def list_due_companies_in_tier_balanced(
    session: Session, now: datetime.datetime, tier_index: int, limit: int, ats_names: list[str]
) -> list[DiscoveredCompany]:
    from core.discovery.interval import tier_bounds

    lower, upper = tier_bounds(tier_index, now)
    if not ats_names:
        return []

    per_domain = max(1, limit // len(ats_names))
    result: list[DiscoveredCompany] = []
    for ats_name in ats_names:
        base = session.query(DiscoveredCompany).filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
            DiscoveredCompany.next_check_at <= now,
            DiscoveredCompany.ats_name == ats_name,
        )

        dated_query = base.filter(DiscoveredCompany.last_activity_at.isnot(None), DiscoveredCompany.last_activity_at <= upper)
        if lower is not None:
            dated_query = dated_query.filter(DiscoveredCompany.last_activity_at > lower)
        dated_rows = dated_query.limit(per_domain).all()

        undated_rows = base.filter(
            DiscoveredCompany.last_activity_at.is_(None), DiscoveredCompany.assigned_tier == tier_index
        ).limit(per_domain).all()

        result.extend((dated_rows + undated_rows)[:per_domain])
    return result[:limit]


def list_due_empty_companies_balanced(
    session: Session, now: datetime.datetime, limit: int, ats_names: list[str]
) -> list[DiscoveredCompany]:
    if not ats_names:
        return []
    per_domain = max(1, limit // len(ats_names))
    result: list[DiscoveredCompany] = []
    for ats_name in ats_names:
        rows = (
            session.query(DiscoveredCompany)
            .filter(
                DiscoveredCompany.active.is_(True),
                DiscoveredCompany.is_deleted.is_(False),
                DiscoveredCompany.last_checked_at.isnot(None),
                DiscoveredCompany.has_ever_had_postings.is_(False),
                DiscoveredCompany.next_check_at <= now,
                DiscoveredCompany.ats_name == ats_name,
            )
            .order_by(DiscoveredCompany.next_check_at.asc())
            .limit(per_domain)
            .all()
        )
        result.extend(rows)
    return result[:limit]


def count_all_active_companies(session: Session) -> int:
    return (
        session.query(DiscoveredCompany)
        .filter(DiscoveredCompany.active.is_(True), DiscoveredCompany.is_deleted.is_(False))
        .count()
    )


def count_companies_by_tier(session: Session, now: datetime.datetime) -> tuple[list[int], int]:
    from core.discovery.interval import TIER_INTERVALS, bucket_index_for_age

    tier_counts = [0] * len(TIER_INTERVALS)

    dated_rows = (
        session.query(DiscoveredCompany.last_activity_at)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
            DiscoveredCompany.last_activity_at.isnot(None),
        )
        .all()
    )
    for (last_activity_at,) in dated_rows:
        tier_counts[bucket_index_for_age(now - last_activity_at)] += 1

    undated_rows = (
        session.query(DiscoveredCompany.assigned_tier, func.count(DiscoveredCompany.id))
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
            DiscoveredCompany.last_activity_at.is_(None),
        )
        .group_by(DiscoveredCompany.assigned_tier)
        .all()
    )
    for tier_index, count in undated_rows:
        index = tier_index if tier_index is not None else len(TIER_INTERVALS) - 1
        tier_counts[index] += count

    empty_count = (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(False),
        )
        .count()
    )

    return tier_counts, empty_count


def count_companies_since(session: Session, since: datetime.datetime) -> int:
    return session.query(DiscoveredCompany).filter(DiscoveredCompany.first_seen_at >= since).count()


def list_companies_in_rank_quantile(
    session: Session, quantile_index: int, quantile_count: int, limit: int
) -> list[DiscoveredCompany]:
    now = datetime.datetime.utcnow()

    live_companies = (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
            DiscoveredCompany.next_check_at <= now,
        )
        .all()
    )

    if not live_companies:
        return []

    dated = [c for c in live_companies if c.last_activity_at is not None]
    undated = [c for c in live_companies if c.last_activity_at is None]

    dated.sort(key=lambda c: c.last_activity_at, reverse=True)

    postings_counts: dict[int, int] = {}
    if undated:
        rows = (
            session.query(DiscoveredJobPosting.company_id, func.count(DiscoveredJobPosting.id))
            .filter(DiscoveredJobPosting.company_id.in_([c.id for c in undated]))
            .group_by(DiscoveredJobPosting.company_id)
            .all()
        )
        postings_counts = dict(rows)
    undated.sort(key=lambda c: postings_counts.get(c.id, 0), reverse=True)

    def _percentile(i: int, n: int) -> float:
        return i / (n - 1) if n > 1 else 0.0

    scored = [(_percentile(i, len(dated)), 0, company) for i, company in enumerate(dated)]
    scored += [(_percentile(i, len(undated)), 1, company) for i, company in enumerate(undated)]
    scored.sort(key=lambda entry: (entry[0], entry[1]))

    ranked = [company for _, _, company in scored]

    total = len(ranked)
    if total == 0:
        return []

    start = (total * quantile_index) // quantile_count
    end = (total * (quantile_index + 1)) // quantile_count
    return ranked[start:end][:limit]


def list_companies_without_postings(session: Session, limit: int) -> list[DiscoveredCompany]:
    return (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(False),
        )
        .order_by(DiscoveredCompany.id.asc())
        .limit(limit)
        .all()
    )


def count_rank_quantile_stats(session: Session) -> dict:
    total_live = (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
        )
        .count()
    )
    total_empty = (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(False),
        )
        .count()
    )
    total_all = total_live + total_empty
    return {"total_all": total_all, "total_live": total_live, "total_empty": total_empty}


def get_quantile_sizes(session: Session, quantile_count: int) -> list[int]:
    total_live = (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.active.is_(True),
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
        )
        .count()
    )
    if total_live == 0:
        return [0] * quantile_count

    sizes = []
    for i in range(quantile_count):
        start = (total_live * i) // quantile_count
        end = (total_live * (i + 1)) // quantile_count
        sizes.append(end - start)
    return sizes


def mark_company_checked(
    session: Session,
    company_id: int,
    next_check_at: datetime.datetime,
    had_new_activity: bool,
    failed: bool = False,
    has_postings: bool | None = None,
    is_deleted: bool = False,
    last_activity_at: datetime.datetime | None = None,
) -> None:
    company = session.get(DiscoveredCompany, company_id)
    if company is None:
        return
    now = datetime.datetime.utcnow()
    company.last_checked_at = now
    company.next_check_at = next_check_at
    if last_activity_at is not None:
        company.last_activity_at = last_activity_at
    if has_postings:
        company.has_ever_had_postings = True
    if is_deleted:
        company.is_deleted = True
    if failed:
        company.consecutive_failures = (company.consecutive_failures or 0) + 1
        if company.consecutive_failures >= 10:
            company.active = False
    else:
        company.consecutive_failures = 0
    session.commit()


def get_existing_external_ids(session: Session, company_id: int) -> set[str]:
    rows = (
        session.query(DiscoveredJobPosting.external_id)
        .filter(DiscoveredJobPosting.company_id == company_id)
        .all()
    )
    return {row[0] for row in rows}


def create_discovered_posting(session: Session, company_id: int, posting: dict) -> DiscoveredJobPosting | None:
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    stmt = sqlite_insert(DiscoveredJobPosting).values(
        company_id=company_id,
        external_id=posting["external_id"],
        url=posting["url"],
        title=posting.get("title"),
        posted_at=posting.get("posted_at"),
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["company_id", "external_id"])
    result = session.execute(stmt)
    session.commit()

    if result.rowcount == 0:
        return None

    return (
        session.query(DiscoveredJobPosting)
        .filter(DiscoveredJobPosting.company_id == company_id, DiscoveredJobPosting.external_id == posting["external_id"])
        .first()
    )


def set_promoted_job_posting(session: Session, discovered_posting_id: int, job_posting_id: int) -> None:
    row = session.get(DiscoveredJobPosting, discovered_posting_id)
    if row is None:
        return
    row.promoted_job_posting_id = job_posting_id
    session.commit()


def get_discovered_posting(session: Session, discovered_posting_id: int) -> DiscoveredJobPosting | None:
    return session.get(DiscoveredJobPosting, discovered_posting_id)


def get_company(session: Session, company_id: int) -> DiscoveredCompany | None:
    return session.get(DiscoveredCompany, company_id)