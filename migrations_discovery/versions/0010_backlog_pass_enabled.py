"""add backlog_pass_enabled to discovery_settings

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "backlog_pass_enabled" not in columns:
        op.add_column("discovery_settings", sa.Column("backlog_pass_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    pass