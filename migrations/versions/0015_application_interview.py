"""add interview_at/interview_notes to applications

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("applications")]
    if "interview_at" not in columns:
        op.add_column("applications", sa.Column("interview_at", sa.DateTime(), nullable=True))
    if "interview_notes" not in columns:
        op.add_column("applications", sa.Column("interview_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    pass