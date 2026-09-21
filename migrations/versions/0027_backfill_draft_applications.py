"""backfill draft applications for already-evaluated jobs created before
auto-draft-application logic existed

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    job_postings = sa.table(
        "job_postings",
        sa.column("id", sa.Integer),
        sa.column("archived", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    evaluations = sa.table("evaluations", sa.column("id", sa.Integer), sa.column("job_posting_id", sa.Integer))
    applications = sa.table(
        "applications",
        sa.column("id", sa.Integer),
        sa.column("job_posting_id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("board_order", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )

    has_eval = sa.exists().where(evaluations.c.job_posting_id == job_postings.c.id)
    has_app = sa.exists().where(applications.c.job_posting_id == job_postings.c.id)

    query = sa.select(job_postings.c.id, job_postings.c.created_at).where(
        sa.or_(job_postings.c.archived.is_(False), job_postings.c.archived.is_(None)),
        has_eval,
        ~has_app,
    )

    rows = bind.execute(query).fetchall()

    for row in rows:
        bind.execute(
            applications.insert().values(
                job_posting_id=row.id,
                status="draft",
                board_order=0,
                created_at=row.created_at,
            )
        )


def downgrade() -> None:
    pass