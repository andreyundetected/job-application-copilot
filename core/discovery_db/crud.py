import datetime

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


def update_settings(session: Session, **kwargs) -> DiscoverySettings:
    settings = get_or_create_settings(session)
    for key, value in kwargs.items():
        if value is not None and hasattr(settings, key):
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


def list_due_companies(session: Session, now: datetime.datetime, limit: int) -> list[DiscoveredCompany]:
    return (
        session.query(DiscoveredCompany)
        .filter(DiscoveredCompany.active.is_(True), DiscoveredCompany.next_check_at <= now)
        .order_by(DiscoveredCompany.next_check_at.asc())
        .limit(limit)
        .all()
    )


def mark_company_checked(
    session: Session,
    company_id: int,
    next_check_at: datetime.datetime,
    had_new_activity: bool,
    failed: bool = False,
) -> None:
    company = session.get(DiscoveredCompany, company_id)
    if company is None:
        return
    now = datetime.datetime.utcnow()
    company.last_checked_at = now
    company.next_check_at = next_check_at
    if had_new_activity:
        company.last_activity_at = now
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


def create_discovered_posting(session: Session, company_id: int, posting: dict) -> DiscoveredJobPosting:
    row = DiscoveredJobPosting(
        company_id=company_id,
        external_id=posting["external_id"],
        url=posting["url"],
        title=posting.get("title"),
        posted_at=posting.get("posted_at"),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


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