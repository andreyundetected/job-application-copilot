"""default auto_tailor_soft/medium_enabled to true, backfill existing row

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("automation_settings") as batch_op:
        batch_op.alter_column(
            "auto_tailor_soft_enabled",
            existing_type=sa.Boolean(),
            server_default=sa.true(),
        )
        batch_op.alter_column(
            "auto_tailor_medium_enabled",
            existing_type=sa.Boolean(),
            server_default=sa.true(),
        )

    # Existing rows (created before this migration existed) were stored with
    # false - the UI had no checkboxes to ever turn them on, so it's safe to
    # bring them in line with the new intended default.
    bind.execute(
        sa.text(
            "UPDATE automation_settings SET auto_tailor_soft_enabled = 1, auto_tailor_medium_enabled = 1"
        )
    )


def downgrade() -> None:
    pass