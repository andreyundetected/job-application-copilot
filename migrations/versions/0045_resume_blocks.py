"""add blocks to resume_versions and tailoring_sessions

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    resume_columns = [col["name"] for col in inspector.get_columns("resume_versions")]
    if "blocks" not in resume_columns:
        op.add_column("resume_versions", sa.Column("blocks", sa.JSON(), nullable=True))

    session_columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]
    if "blocks" not in session_columns:
        op.add_column("tailoring_sessions", sa.Column("blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass