"""add preferred_currency/preferred_salary_period to app_settings

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("app_settings")]

    if "preferred_currency" not in columns:
        op.add_column(
            "app_settings", sa.Column("preferred_currency", sa.String(8), nullable=True, server_default="USD")
        )
    if "preferred_salary_period" not in columns:
        op.add_column(
            "app_settings", sa.Column("preferred_salary_period", sa.String(8), nullable=True, server_default="year")
        )


def downgrade() -> None:
    pass