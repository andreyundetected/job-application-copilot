"""add board_order to applications for manual drag reordering

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("applications")]

    if "board_order" not in columns:
        op.add_column("applications", sa.Column("board_order", sa.Integer(), nullable=True, server_default="0"))

    applications_table = sa.table(
        "applications",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("board_order", sa.Integer),
    )

    rows = bind.execute(
        sa.text("SELECT id, status FROM applications ORDER BY status, created_at DESC")
    ).fetchall()

    counters: dict[str, int] = {}
    for row in rows:
        index = counters.get(row.status, 0)
        bind.execute(
            applications_table.update()
            .where(applications_table.c.id == row.id)
            .values(board_order=index)
        )
        counters[row.status] = index + 1


def downgrade() -> None:
    pass