from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("tailoring_letters")]

    if "comment" not in columns:
        op.add_column("tailoring_letters", sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    pass