"""add auto_tailor_master_enabled and auto_questions_master_enabled to automation_settings

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("automation_settings")]

    if "auto_tailor_master_enabled" not in columns:
        op.add_column(
            "automation_settings",
            sa.Column("auto_tailor_master_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
        )
    if "auto_questions_master_enabled" not in columns:
        op.add_column(
            "automation_settings",
            sa.Column("auto_questions_master_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
        )


def downgrade() -> None:
    pass