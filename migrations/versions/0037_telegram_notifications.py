"""add telegram notification fields to app_settings

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("app_settings")]

    if "telegram_bot_token" not in columns:
        op.add_column("app_settings", sa.Column("telegram_bot_token", sa.String(255), nullable=True))
    if "telegram_chat_id" not in columns:
        op.add_column("app_settings", sa.Column("telegram_chat_id", sa.String(128), nullable=True))
    if "telegram_notify_enabled" not in columns:
        op.add_column(
            "app_settings", sa.Column("telegram_notify_enabled", sa.Boolean(), nullable=True, server_default=sa.false())
        )
    if "telegram_notify_only_successful" not in columns:
        op.add_column(
            "app_settings",
            sa.Column("telegram_notify_only_successful", sa.Boolean(), nullable=True, server_default=sa.true()),
        )
    if "telegram_notify_min_score" not in columns:
        op.add_column("app_settings", sa.Column("telegram_notify_min_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    pass