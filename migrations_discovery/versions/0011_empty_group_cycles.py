"""add empty_group_check_every_n_cycles to discovery_settings

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "empty_group_check_every_n_cycles" not in columns:
        op.add_column(
            "discovery_settings",
            sa.Column("empty_group_check_every_n_cycles", sa.Integer(), nullable=True, server_default="10"),
        )


def downgrade() -> None:
    pass