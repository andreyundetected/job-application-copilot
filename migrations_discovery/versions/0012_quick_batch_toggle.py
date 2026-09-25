"""replace passive_mode with quick_batch_enabled on discovery_settings

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovery_settings")]

    if "quick_batch_enabled" not in columns:
        op.add_column(
            "discovery_settings",
            sa.Column("quick_batch_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        )

    if "passive_mode" in columns:
        bind.execute(sa.text("UPDATE discovery_settings SET quick_batch_enabled = NOT passive_mode"))
        with op.batch_alter_table("discovery_settings") as batch_op:
            batch_op.drop_column("passive_mode")


def downgrade() -> None:
    pass