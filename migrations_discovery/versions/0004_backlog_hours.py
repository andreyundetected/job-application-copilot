"""add initial_backlog_hours to discovery_settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "initial_backlog_hours" not in columns:
        op.add_column(
            "discovery_settings", sa.Column("initial_backlog_hours", sa.Integer(), nullable=True, server_default="2")
        )


def downgrade() -> None:
    pass