"""add activity_label to job_postings for live progress indicator

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("job_postings")]

    if "activity_label" not in columns:
        op.add_column("job_postings", sa.Column("activity_label", sa.String(255), nullable=True))


def downgrade() -> None:
    pass