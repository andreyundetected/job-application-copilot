"""add retry/stuck tracking to job_postings and form_questions

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    job_columns = [col["name"] for col in inspector.get_columns("job_postings")]
    if "retry_count" not in job_columns:
        op.add_column("job_postings", sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"))
    if "activity_started_at" not in job_columns:
        op.add_column("job_postings", sa.Column("activity_started_at", sa.DateTime(), nullable=True))

    question_columns = [col["name"] for col in inspector.get_columns("form_questions")]
    if "retry_count" not in question_columns:
        op.add_column("form_questions", sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"))
    if "pending_started_at" not in question_columns:
        op.add_column("form_questions", sa.Column("pending_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    pass