"""drop next_check_at from discovered_companies

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("discovered_companies")]
    if "next_check_at" not in columns:
        return

    index_names = [index["name"] for index in inspector.get_indexes("discovered_companies")]

    with op.batch_alter_table("discovered_companies") as batch_op:
        if "ix_discovered_companies_next_check_at" in index_names:
            batch_op.drop_index("ix_discovered_companies_next_check_at")
        batch_op.drop_column("next_check_at")


def downgrade() -> None:
    pass