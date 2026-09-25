"""add has_ever_had_postings and is_deleted to discovered_companies

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("discovered_companies")]

    if "has_ever_had_postings" not in columns:
        op.add_column(
            "discovered_companies", sa.Column("has_ever_had_postings", sa.Boolean(), nullable=True, server_default=sa.false())
        )
    if "is_deleted" not in columns:
        op.add_column(
            "discovered_companies", sa.Column("is_deleted", sa.Boolean(), nullable=True, server_default=sa.false())
        )


def downgrade() -> None:
    pass