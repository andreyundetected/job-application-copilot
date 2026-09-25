"""add discarded_by_quick_screen to discovered_job_postings

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovered_job_postings")]

    if "discarded_by_quick_screen" not in columns:
        op.add_column("discovered_job_postings", sa.Column("discarded_by_quick_screen", sa.Boolean(), nullable=True))


def downgrade() -> None:
    pass