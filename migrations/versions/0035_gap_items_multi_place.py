"""gap_items: multi-location assignment + over-item keep recommendation

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("gap_items")]

    if "suggested_field_paths" not in columns:
        op.add_column("gap_items", sa.Column("suggested_field_paths", sa.JSON(), nullable=True))
    if "assigned_field_paths" not in columns:
        op.add_column("gap_items", sa.Column("assigned_field_paths", sa.JSON(), nullable=True))
    if "recommend_keep" not in columns:
        op.add_column("gap_items", sa.Column("recommend_keep", sa.Boolean(), nullable=True))


def downgrade() -> None:
    pass