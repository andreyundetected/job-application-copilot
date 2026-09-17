"""add question_changes table, referenced_question_id on chat messages

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "application_chat_messages" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("application_chat_messages")]
        if "referenced_question_id" not in columns:
            op.add_column(
                "application_chat_messages",
                sa.Column("referenced_question_id", sa.Integer(), sa.ForeignKey("form_questions.id"), nullable=True),
            )

    if "question_changes" not in existing_tables:
        op.create_table(
            "question_changes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("form_questions.id"), nullable=False),
            sa.Column("chat_message_id", sa.Integer(), sa.ForeignKey("application_chat_messages.id"), nullable=True),
            sa.Column("original_text", sa.Text(), nullable=True),
            sa.Column("proposed_text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=True),
        )


def downgrade() -> None:
    pass