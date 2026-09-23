"""add catch_all_enabled/max_pages_per_query to automation_settings

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("automation_settings")]

    if "catch_all_enabled" not in columns:
        op.add_column(
            "automation_settings", sa.Column("catch_all_enabled", sa.Boolean(), nullable=True, server_default=sa.true())
        )
    if "max_pages_per_query" not in columns:
        op.add_column(
            "automation_settings", sa.Column("max_pages_per_query", sa.Integer(), nullable=True, server_default="10")
        )


def downgrade() -> None:
    pass