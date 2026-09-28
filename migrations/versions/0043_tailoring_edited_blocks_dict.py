"""add edited_blocks (dict: field_path -> original_text) to tailoring_sessions,
replacing the list-only edited_block_paths from 0041

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]

    if "edited_blocks" not in columns:
        op.add_column("tailoring_sessions", sa.Column("edited_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass