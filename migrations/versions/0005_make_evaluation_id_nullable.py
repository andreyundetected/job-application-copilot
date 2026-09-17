"""make tailoring_changes.evaluation_id nullable

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tailoring_changes") as batch_op:
        batch_op.alter_column(
            "evaluation_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    pass