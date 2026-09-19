"""backfill NULL target_sites/saved_queries and dedupe automation_settings rows

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-19

"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_DEFAULT_TARGET_SITES = json.dumps(["boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"])


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "DELETE FROM automation_settings WHERE id NOT IN "
            "(SELECT MIN(id) FROM automation_settings)"
        )
    )
    bind.execute(
        sa.text("UPDATE automation_settings SET target_sites = :sites WHERE target_sites IS NULL"),
        {"sites": _DEFAULT_TARGET_SITES},
    )
    bind.execute(
        sa.text("UPDATE automation_settings SET saved_queries = '[]' WHERE saved_queries IS NULL")
    )


def downgrade() -> None:
    pass