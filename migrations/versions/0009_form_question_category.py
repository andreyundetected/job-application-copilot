"""add category, order, needs_manual_input to form_questions

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("form_questions")]

    if "category" not in columns:
        op.add_column("form_questions", sa.Column("category", sa.String(32), nullable=True))
    if "order" not in columns:
        op.add_column("form_questions", sa.Column("order", sa.Integer(), nullable=True, server_default="0"))
    if "needs_manual_input" not in columns:
        op.add_column(
            "form_questions", sa.Column("needs_manual_input", sa.Boolean(), nullable=True, server_default=sa.false())
        )


def downgrade() -> None:
    pass