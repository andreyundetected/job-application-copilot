"""add disabled_field_paths to gap_items

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("gap_items")]

    if "disabled_field_paths" not in columns:
        op.add_column("gap_items", sa.Column("disabled_field_paths", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass