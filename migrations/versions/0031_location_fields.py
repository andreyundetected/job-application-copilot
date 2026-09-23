"""add location_country/state/city to job_postings

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("job_postings")]

    if "location_country" not in columns:
        op.add_column("job_postings", sa.Column("location_country", sa.String(255), nullable=True))
    if "location_state" not in columns:
        op.add_column("job_postings", sa.Column("location_state", sa.String(255), nullable=True))
    if "location_city" not in columns:
        op.add_column("job_postings", sa.Column("location_city", sa.String(255), nullable=True))


def downgrade() -> None:
    pass