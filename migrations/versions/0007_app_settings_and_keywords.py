"""add app_settings table and extracted_keywords column

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "app_settings" not in existing_tables:
        op.create_table(
            "app_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pregenerate_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("pregenerate_min_score", sa.Integer(), nullable=True, server_default="7"),
        )

    session_columns = [col["name"] for col in inspector.get_columns("tailoring_sessions")]
    if "extracted_keywords" not in session_columns:
        op.add_column("tailoring_sessions", sa.Column("extracted_keywords", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass