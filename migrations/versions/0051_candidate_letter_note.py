from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("candidate_profile")]

    if "letter_note" not in columns:
        op.add_column("candidate_profile", sa.Column("letter_note", sa.Text(), nullable=True))


def downgrade() -> None:
    pass