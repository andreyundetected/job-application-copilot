"""add tailoring sessions, messages, permissions

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "tailoring_sessions" not in existing_tables:
        op.create_table(
            "tailoring_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
            sa.Column("resume_version_id", sa.Integer(), sa.ForeignKey("resume_versions.id"), nullable=False),
            sa.Column("working_content", sa.JSON(), nullable=False),
            sa.Column("style", sa.JSON(), nullable=True),
        )

    if "tailoring_messages" not in existing_tables:
        op.create_table(
            "tailoring_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("tailoring_sessions.id"), nullable=False),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
        )

    if "tailoring_permissions" not in existing_tables:
        op.create_table(
            "tailoring_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("level", sa.String(16), nullable=False),
            sa.Column("change_type", sa.String(64), nullable=False),
            sa.Column("auto_apply", sa.Boolean(), nullable=True),
        )

    change_columns = [col["name"] for col in inspector.get_columns("tailoring_changes")]

    with op.batch_alter_table("tailoring_changes") as batch_op:
        if "session_id" not in change_columns:
            batch_op.add_column(sa.Column("session_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_tailoring_changes_session_id",
                "tailoring_sessions",
                ["session_id"],
                ["id"],
            )
        if "message_id" not in change_columns:
            batch_op.add_column(sa.Column("message_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_tailoring_changes_message_id",
                "tailoring_messages",
                ["message_id"],
                ["id"],
            )
        if "field_path" not in change_columns:
            batch_op.add_column(sa.Column("field_path", sa.String(255), nullable=True))
        if "proposed_content" not in change_columns:
            batch_op.add_column(sa.Column("proposed_content", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass