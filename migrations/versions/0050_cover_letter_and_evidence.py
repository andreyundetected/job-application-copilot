from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    gap_columns = [col["name"] for col in inspector.get_columns("gap_items")]
    if "evidence" not in gap_columns:
        op.add_column("gap_items", sa.Column("evidence", sa.String(1000), nullable=True))

    if "tailoring_letters" not in inspector.get_table_names():
        op.create_table(
            "tailoring_letters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False, unique=True, index=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    pass