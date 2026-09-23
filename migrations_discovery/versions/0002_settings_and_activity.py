"""add discovery_settings table and last_activity_at on discovered_companies

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    company_columns = [col["name"] for col in inspector.get_columns("discovered_companies")]
    if "last_activity_at" not in company_columns:
        op.add_column("discovered_companies", sa.Column("last_activity_at", sa.DateTime(), nullable=True))

    if "discovery_settings" not in existing_tables:
        op.create_table(
            "discovery_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("wayback_interval_hours", sa.Integer(), nullable=True, server_default="168"),
            sa.Column("last_wayback_run_at", sa.DateTime(), nullable=True),
            sa.Column("notify_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("notify_only_successful", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("notify_min_score", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    pass