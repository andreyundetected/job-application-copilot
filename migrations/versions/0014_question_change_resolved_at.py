"""add resolved_at to question_changes

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("question_changes")]
    if "resolved_at" not in columns:
        op.add_column("question_changes", sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    pass