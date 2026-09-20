"""add question_templates table and template fields on form_questions

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-20

"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "question_templates" not in existing_tables:
        op.create_table(
            "question_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("label", sa.String(128), nullable=False),
            sa.Column("trigger_phrases", sa.JSON(), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=True, server_default="0"),
        )

    columns = [col["name"] for col in inspector.get_columns("form_questions")]
    if "template_label" not in columns:
        op.add_column("form_questions", sa.Column("template_label", sa.String(128), nullable=True))
    if "template_instructions" not in columns:
        op.add_column("form_questions", sa.Column("template_instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    pass