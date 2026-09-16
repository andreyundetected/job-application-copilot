"""add tailoring_changes table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tailoring_changes" not in inspector.get_table_names():
        op.create_table(
            "tailoring_changes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id"), nullable=False),
            sa.Column("level", sa.String(16), nullable=False),
            sa.Column("change_type", sa.String(32), nullable=False),
            sa.Column("target_ref", sa.String(255), nullable=True),
            sa.Column("original_text", sa.Text(), nullable=True),
            sa.Column("proposed_text", sa.Text(), nullable=False),
            sa.Column("final_text", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=True),
            sa.Column("order", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    pass