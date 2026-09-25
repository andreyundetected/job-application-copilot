"""add batch_force_flush_size to discovery_settings

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "batch_force_flush_size" not in columns:
        op.add_column(
            "discovery_settings",
            sa.Column("batch_force_flush_size", sa.Integer(), nullable=True, server_default="25"),
        )


def downgrade() -> None:
    pass