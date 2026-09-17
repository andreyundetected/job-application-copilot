"""add full_name to candidate_profile

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profile_columns = [col["name"] for col in inspector.get_columns("candidate_profile")]
    if "full_name" not in profile_columns:
        op.add_column("candidate_profile", sa.Column("full_name", sa.String(255), nullable=True))


def downgrade() -> None:
    pass