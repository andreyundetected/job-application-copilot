"""add content_html / working_html for raw-text-based resume storage

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    resume_columns = [col["name"] for col in inspector.get_columns("resume_versions")]
    if "content_html" not in resume_columns:
        op.add_column("resume_versions", sa.Column("content_html", sa.Text(), nullable=True))

    session_columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]
    if "working_html" not in session_columns:
        op.add_column("tailoring_sessions", sa.Column("working_html", sa.Text(), nullable=True))


def downgrade() -> None:
    pass