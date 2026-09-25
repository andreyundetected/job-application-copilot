"""add batch_window_minutes to discovery_settings

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "batch_window_minutes" not in columns:
        op.add_column("discovery_settings", sa.Column("batch_window_minutes", sa.Integer(), nullable=True, server_default="15"))


def downgrade() -> None:
    pass