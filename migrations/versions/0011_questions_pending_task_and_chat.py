"""add pending_task_id to form_questions, add application_chat_messages

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("form_questions")]
    if "pending_task_id" not in columns:
        op.add_column("form_questions", sa.Column("pending_task_id", sa.Integer(), nullable=True))

    if "application_chat_messages" not in inspector.get_table_names():
        op.create_table(
            "application_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("referenced_question_ids", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    pass