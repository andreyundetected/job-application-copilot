"""drop unused form_question_messages table

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "form_question_messages" in inspector.get_table_names():
        op.drop_table("form_question_messages")


def downgrade() -> None:
    pass