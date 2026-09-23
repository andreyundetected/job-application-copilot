import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class DiscoveryBase(DeclarativeBase):
    pass


class DiscoveredCompany(DiscoveryBase):
    __tablename__ = "discovered_companies"
    __table_args__ = (UniqueConstraint("ats_name", "slug", name="uq_discovered_company_ats_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    ats_name: Mapped[str] = mapped_column(String(32), index=True)
    slug: Mapped[str] = mapped_column(String(255))

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    last_checked_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    next_check_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamp of the most recent NEW posting found for this company - drives
    # the adaptive check frequency (see core/discovery/interval.py). Defaults
    # to first_seen_at so a brand-new company starts in the most frequent bucket.
    last_activity_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    postings: Mapped[list["DiscoveredJobPosting"]] = relationship(back_populates="company")


class DiscoverySettings(DiscoveryBase):
    __tablename__ = "discovery_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    wayback_interval_hours: Mapped[int] = mapped_column(Integer, default=168)
    last_wayback_run_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    initial_backlog_hours: Mapped[int] = mapped_column(Integer, default=2)

    notify_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_only_successful: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_min_score: Mapped[int] = mapped_column(Integer, nullable=True)


class DiscoveredJobPosting(DiscoveryBase):
    __tablename__ = "discovered_job_postings"
    __table_args__ = (
        UniqueConstraint("company_id", "external_id", name="uq_discovered_posting_company_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    company_id: Mapped[int] = mapped_column(ForeignKey("discovered_companies.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(512), nullable=True)

    posted_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    promoted_job_posting_id: Mapped[int] = mapped_column(Integer, nullable=True)

    company: Mapped["DiscoveredCompany"] = relationship(back_populates="postings")