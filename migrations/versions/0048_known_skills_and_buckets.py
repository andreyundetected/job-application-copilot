"""known skills, keyword bucket fields on gap_items, skills popup choice

Revision ID: 0048
Revises: 0047
Create Date: 2026-10-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "known_skills" not in inspector.get_table_names():
        op.create_table(
            "known_skills",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("text", sa.String(255), nullable=False),
            sa.Column("text_norm", sa.String(255), nullable=False, unique=True),
        )

    gap_columns = [col["name"] for col in inspector.get_columns("gap_items")]
    if "resume_form" not in gap_columns:
        op.add_column("gap_items", sa.Column("resume_form", sa.String(255), nullable=True))
    if "suggested_form" not in gap_columns:
        op.add_column("gap_items", sa.Column("suggested_form", sa.String(255), nullable=True))

    settings_columns = [col["name"] for col in inspector.get_columns("app_settings")]
    if "skills_popup_choice" not in settings_columns:
        op.add_column("app_settings", sa.Column("skills_popup_choice", sa.String(8), nullable=True))


def downgrade() -> None:
    pass