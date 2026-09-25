"""add passive_mode and initial_collection_done_at to discovery_settings

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "passive_mode" not in columns:
        op.add_column("discovery_settings", sa.Column("passive_mode", sa.Boolean(), nullable=True, server_default=sa.false()))
    if "initial_collection_done_at" not in columns:
        op.add_column("discovery_settings", sa.Column("initial_collection_done_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    pass