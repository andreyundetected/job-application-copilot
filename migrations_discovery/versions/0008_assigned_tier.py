"""add assigned_tier to discovered_companies

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24

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
    columns = [col["name"] for col in inspector.get_columns("discovered_companies")]

    if "assigned_tier" not in columns:
        op.add_column("discovered_companies", sa.Column("assigned_tier", sa.Integer(), nullable=True))


def downgrade() -> None:
    pass