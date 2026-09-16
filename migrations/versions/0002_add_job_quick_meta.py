"""add quick-extract fields to job_postings

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = [col["name"] for col in inspector.get_columns("job_postings")]

    if "location" not in existing_columns:
        op.add_column("job_postings", sa.Column("location", sa.String(255), nullable=True))
    if "work_mode" not in existing_columns:
        op.add_column("job_postings", sa.Column("work_mode", sa.String(32), nullable=True))
    if "employment_type" not in existing_columns:
        op.add_column("job_postings", sa.Column("employment_type", sa.String(64), nullable=True))
    if "tags" not in existing_columns:
        op.add_column("job_postings", sa.Column("tags", sa.JSON(), nullable=True))
    if "pending_task_id" not in existing_columns:
        op.add_column("job_postings", sa.Column("pending_task_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    pass