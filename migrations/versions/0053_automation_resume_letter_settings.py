from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("auto_letter_master_enabled", sa.false()),
    ("auto_apply_title_main", sa.true()),
    ("auto_apply_exp_titles", sa.true()),
    ("auto_apply_summary", sa.true()),
    ("auto_apply_skills", sa.true()),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = [col["name"] for col in inspector.get_columns("automation_settings")]

    for name, default in _COLUMNS:
        if name not in existing:
            op.add_column(
                "automation_settings",
                sa.Column(name, sa.Boolean(), nullable=True, server_default=default),
            )


def downgrade() -> None:
    pass