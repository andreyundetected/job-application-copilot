"""add triggered_blockers to evaluations

Revision ID: 0047
Revises: 0046
Create Date: 2026-10-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("evaluations")]

    if "triggered_blockers" not in columns:
        op.add_column("evaluations", sa.Column("triggered_blockers", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass