"""add manual_assist_tailoring_permissions and manual_assist_base_questions

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "manual_assist_tailoring_permissions" not in existing_tables:
        op.create_table(
            "manual_assist_tailoring_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("level", sa.String(16), nullable=False),
            sa.Column("change_type", sa.String(64), nullable=False),
            sa.Column("auto_apply", sa.Boolean(), nullable=True, server_default=sa.false()),
        )

    if "manual_assist_base_questions" not in existing_tables:
        op.create_table(
            "manual_assist_base_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=True, server_default="0"),
        )


def downgrade() -> None:
    pass