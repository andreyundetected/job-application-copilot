"""add auto_answer_questions_enabled to app_settings

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("app_settings")]
    if "auto_answer_questions_enabled" not in columns:
        op.add_column(
            "app_settings",
            sa.Column("auto_answer_questions_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        )


def downgrade() -> None:
    pass