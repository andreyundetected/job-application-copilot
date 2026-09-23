"""initial discovery schema: discovered_companies, discovered_job_postings

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "discovered_companies" not in existing_tables:
        op.create_table(
            "discovered_companies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("ats_name", sa.String(32), nullable=False),
            sa.Column("slug", sa.String(255), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("first_seen_at", sa.DateTime(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("next_check_at", sa.DateTime(), nullable=True),
            sa.Column("consecutive_failures", sa.Integer(), nullable=True, server_default="0"),
            sa.UniqueConstraint("ats_name", "slug", name="uq_discovered_company_ats_slug"),
        )
        op.create_index("ix_discovered_companies_ats_name", "discovered_companies", ["ats_name"])
        op.create_index("ix_discovered_companies_next_check_at", "discovered_companies", ["next_check_at"])

    if "discovered_job_postings" not in existing_tables:
        op.create_table(
            "discovered_job_postings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("discovered_companies.id"), nullable=False),
            sa.Column("external_id", sa.String(255), nullable=False),
            sa.Column("url", sa.String(1024), nullable=False),
            sa.Column("title", sa.String(512), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("first_seen_at", sa.DateTime(), nullable=True),
            sa.Column("promoted_job_posting_id", sa.Integer(), nullable=True),
            sa.UniqueConstraint(
                "company_id", "external_id", name="uq_discovered_posting_company_external_id"
            ),
        )
        op.create_index("ix_discovered_job_postings_company_id", "discovered_job_postings", ["company_id"])


def downgrade() -> None:
    pass