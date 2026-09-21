"""add automation_base_questions table

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "automation_base_questions" not in inspector.get_table_names():
        op.create_table(
            "automation_base_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=True, server_default="0"),
        )


def downgrade() -> None:
    pass