"""add gap_items table and block comments on tailoring_sessions

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "gap_items" not in existing_tables:
        op.create_table(
            "gap_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("tailoring_sessions.id"), nullable=False),
            sa.Column("text", sa.String(255), nullable=False),
            sa.Column("category", sa.String(32), nullable=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("priority", sa.String(16), nullable=True),
            sa.Column("source", sa.String(16), nullable=True),
            sa.Column("original_field_path", sa.String(255), nullable=True),
            sa.Column("suggested_field_path", sa.String(255), nullable=True),
            sa.Column("suggested_reason", sa.Text(), nullable=True),
            sa.Column("assigned_field_path", sa.String(255), nullable=True),
            sa.Column("included", sa.Boolean(), nullable=True, server_default=sa.false()),
        )

    session_columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]
    if "block_comments" not in session_columns:
        op.add_column("tailoring_sessions", sa.Column("block_comments", sa.JSON(), nullable=True))
    if "gap_analysis_ready" not in session_columns:
        op.add_column(
            "tailoring_sessions",
            sa.Column("gap_analysis_ready", sa.Boolean(), nullable=True, server_default=sa.false()),
        )


def downgrade() -> None:
    pass