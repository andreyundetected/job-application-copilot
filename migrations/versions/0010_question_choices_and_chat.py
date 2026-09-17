"""add choice/char_limit/flag_reason to form_questions, add form_question_messages

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("form_questions")]

    if "options" not in columns:
        op.add_column("form_questions", sa.Column("options", sa.JSON(), nullable=True))
    if "selected_option" not in columns:
        op.add_column("form_questions", sa.Column("selected_option", sa.String(255), nullable=True))
    if "char_limit" not in columns:
        op.add_column("form_questions", sa.Column("char_limit", sa.Integer(), nullable=True))
    if "flag_reason" not in columns:
        op.add_column("form_questions", sa.Column("flag_reason", sa.Text(), nullable=True))

    if "form_question_messages" not in inspector.get_table_names():
        op.create_table(
            "form_question_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("form_questions.id"), nullable=False),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    pass