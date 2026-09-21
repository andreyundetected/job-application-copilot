"""automation settings cleanup: drop target_sites/max_query_words/auto_tailor_*_enabled,
bump default results-per-query to 100

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("automation_settings")]

    with op.batch_alter_table("automation_settings") as batch_op:
        if "target_sites" in columns:
            batch_op.drop_column("target_sites")
        if "max_query_words" in columns:
            batch_op.drop_column("max_query_words")
        if "auto_tailor_soft_enabled" in columns:
            batch_op.drop_column("auto_tailor_soft_enabled")
        if "auto_tailor_medium_enabled" in columns:
            batch_op.drop_column("auto_tailor_medium_enabled")

    bind.execute(
        sa.text(
            "UPDATE automation_settings SET serpent_num_per_query = 100 "
            "WHERE serpent_num_per_query IS NULL OR serpent_num_per_query = 30"
        )
    )


def downgrade() -> None:
    pass