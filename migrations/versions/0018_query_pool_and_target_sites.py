"""replace query_chunk_size with target_sites and max_query_words

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("automation_settings")]

    if "target_sites" not in columns:
        op.add_column("automation_settings", sa.Column("target_sites", sa.JSON(), nullable=True))
    if "max_query_words" not in columns:
        op.add_column(
            "automation_settings",
            sa.Column("max_query_words", sa.Integer(), nullable=True, server_default="32"),
        )

    if "query_chunk_size" in columns:
        with op.batch_alter_table("automation_settings") as batch_op:
            batch_op.drop_column("query_chunk_size")


def downgrade() -> None:
    pass