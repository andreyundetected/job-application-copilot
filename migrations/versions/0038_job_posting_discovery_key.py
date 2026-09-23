"""add discovery_key to job_postings for dedup against discovered postings

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("job_postings")]

    if "discovery_key" not in columns:
        op.add_column("job_postings", sa.Column("discovery_key", sa.String(64), nullable=True))
        op.create_index(
            "uq_job_postings_discovery_key", "job_postings", ["discovery_key"], unique=True
        )


def downgrade() -> None:
    pass