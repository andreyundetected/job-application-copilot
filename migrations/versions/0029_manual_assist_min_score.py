"""add manual_assist_min_score to app_settings

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("app_settings")]
    if "manual_assist_min_score" not in columns:
        op.add_column(
            "app_settings",
            sa.Column("manual_assist_min_score", sa.Integer(), nullable=True, server_default="7"),
        )


def downgrade() -> None:
    pass