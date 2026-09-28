"""add edited_block_paths to tailoring_sessions

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]

    if "edited_block_paths" not in columns:
        op.add_column("tailoring_sessions", sa.Column("edited_block_paths", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass