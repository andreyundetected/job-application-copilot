from alembic import op
import sqlalchemy as sa

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "title_rejections" not in inspector.get_table_names():
        op.create_table(
            "title_rejections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(16), nullable=True),
            sa.Column("original", sa.String(500), nullable=False),
            sa.Column("rejected", sa.String(500), nullable=False),
            sa.Column("comment", sa.String(2000), nullable=True),
        )


def downgrade() -> None:
    pass