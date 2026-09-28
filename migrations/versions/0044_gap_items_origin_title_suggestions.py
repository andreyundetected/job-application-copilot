"""add origin_status to gap_items, title_suggestions to tailoring_sessions

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    gap_item_columns = [col["name"] for col in inspector.get_columns("gap_items")]
    if "origin_status" not in gap_item_columns:
        op.add_column("gap_items", sa.Column("origin_status", sa.String(16), nullable=True))

    session_columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]
    if "title_suggestions" not in session_columns:
        op.add_column("tailoring_sessions", sa.Column("title_suggestions", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass