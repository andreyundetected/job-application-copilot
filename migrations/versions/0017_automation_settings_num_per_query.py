"""add serpent_num_per_query to automation_settings

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("automation_settings")]
    if "serpent_num_per_query" not in columns:
        op.add_column(
            "automation_settings",
            sa.Column("serpent_num_per_query", sa.Integer(), nullable=True, server_default="30"),
        )


def downgrade() -> None:
    pass