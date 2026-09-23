"""add writing_preferences to candidate_profile

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("candidate_profile")]

    if "writing_preferences" not in columns:
        op.add_column("candidate_profile", sa.Column("writing_preferences", sa.Text(), nullable=True))


def downgrade() -> None:
    pass