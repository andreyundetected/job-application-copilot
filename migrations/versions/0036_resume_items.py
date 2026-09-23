"""add resume_items to tailoring_sessions

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]

    if "resume_items" not in columns:
        op.add_column("tailoring_sessions", sa.Column("resume_items", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass