"""catch up schema to current models

Revision ID: 0001
Revises:
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = inspector.get_table_names()

    if "job_postings" in existing_tables:
        job_posting_columns = [col["name"] for col in inspector.get_columns("job_postings")]
        if "archived" not in job_posting_columns:
            op.add_column(
                "job_postings", sa.Column("archived", sa.Boolean(), nullable=True, server_default=sa.false())
            )

    if "resume_versions" in existing_tables:
        resume_columns = [col["name"] for col in inspector.get_columns("resume_versions")]
        if "structured_content" not in resume_columns:
            op.add_column("resume_versions", sa.Column("structured_content", sa.JSON(), nullable=True))
        if "is_active" not in resume_columns:
            op.add_column(
                "resume_versions", sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.false())
            )

    if "blocker_rules" not in existing_tables:
        op.create_table(
            "blocker_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=True),
        )

    if "scoring_factors" not in existing_tables:
        op.create_table(
            "scoring_factors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("direction", sa.String(8), nullable=False),
            sa.Column("weight", sa.Integer(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=True),
        )

    if "candidate_profile" not in existing_tables:
        op.create_table(
            "candidate_profile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("github_url", sa.String(512), nullable=True),
            sa.Column("linkedin_url", sa.String(512), nullable=True),
            sa.Column("extra_links", sa.JSON(), nullable=True),
            sa.Column("extra_info", sa.Text(), nullable=True),
        )

    if "task_statuses" not in existing_tables:
        op.create_table(
            "task_statuses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("task_type", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    pass