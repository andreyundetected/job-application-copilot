"""flip discovery_settings.enabled default to false, disable existing row

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("discovery_settings") as batch_op:
        batch_op.alter_column("enabled", existing_type=sa.Boolean(), server_default=sa.false())

    bind.execute(sa.text("UPDATE discovery_settings SET enabled = 0"))


def downgrade() -> None:
    pass