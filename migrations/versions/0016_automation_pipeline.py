"""add automation pipeline tables and job posting automation fields

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    job_posting_columns = [col["name"] for col in inspector.get_columns("job_postings")]
    if "source" not in job_posting_columns:
        op.add_column(
            "job_postings",
            sa.Column("source", sa.String(16), nullable=True, server_default="manual"),
        )
    if "pipeline_stage" not in job_posting_columns:
        op.add_column("job_postings", sa.Column("pipeline_stage", sa.String(32), nullable=True))

    if "automation_runs" not in existing_tables:
        op.create_table(
            "automation_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(16), nullable=True, server_default="pending"),
            sa.Column("queries_planned", sa.JSON(), nullable=True),
            sa.Column("max_results_override", sa.Integer(), nullable=True),
            sa.Column("max_queries_override", sa.Integer(), nullable=True),
            sa.Column("found_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("quick_filtered_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("scraped_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("evaluated_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("passed_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("archived_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
        )

    if "search_results" not in existing_tables:
        op.create_table(
            "search_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column(
                "automation_run_id",
                sa.Integer(),
                sa.ForeignKey("automation_runs.id"),
                nullable=False,
            ),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("source_platform", sa.String(32), nullable=True),
            sa.Column("title", sa.String(512), nullable=True),
            sa.Column("snippet", sa.Text(), nullable=True),
            sa.Column("url", sa.String(1024), nullable=False),
            sa.Column("url_normalized", sa.String(1024), nullable=False, unique=True),
            sa.Column("quick_filter_verdict", sa.String(16), nullable=True),
            sa.Column(
                "promoted_job_posting_id",
                sa.Integer(),
                sa.ForeignKey("job_postings.id"),
                nullable=True,
            ),
        )

    if "automation_settings" not in existing_tables:
        op.create_table(
            "automation_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("min_score_to_proceed", sa.Integer(), nullable=True, server_default="6"),
            sa.Column("max_score_to_archive", sa.Integer(), nullable=True, server_default="3"),
            sa.Column("quick_filter_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("auto_archive_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("auto_tailor_soft_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("auto_tailor_medium_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("query_chunk_size", sa.Integer(), nullable=True, server_default="8"),
            sa.Column("default_time_range", sa.String(8), nullable=True, server_default="w1"),
            sa.Column("saved_queries", sa.JSON(), nullable=True),
            sa.Column("serpent_cost_per_request", sa.Float(), nullable=True),
        )

    if "api_usage_log" not in existing_tables:
        op.create_table(
            "api_usage_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("operation", sa.String(32), nullable=False),
            sa.Column(
                "automation_run_id", sa.Integer(), sa.ForeignKey("automation_runs.id"), nullable=True
            ),
            sa.Column(
                "search_result_id", sa.Integer(), sa.ForeignKey("search_results.id"), nullable=True
            ),
            sa.Column(
                "job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=True
            ),
            sa.Column("requested_num", sa.Integer(), nullable=True),
            sa.Column("returned_count", sa.Integer(), nullable=True),
            sa.Column("model", sa.String(128), nullable=True),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("estimated_cost", sa.Float(), nullable=True),
            sa.Column("raw_usage", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    pass