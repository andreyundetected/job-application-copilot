"""remove section blocks from resume_versions.blocks and tailoring_sessions.blocks

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-28

"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def _strip_sections(bind, table_name: str) -> None:
    table = sa.table(table_name, sa.column("id", sa.Integer), sa.column("blocks", sa.JSON))
    rows = bind.execute(sa.select(table.c.id, table.c.blocks)).fetchall()
    for row in rows:
        blocks = row.blocks
        if isinstance(blocks, str):
            blocks = json.loads(blocks)
        if not isinstance(blocks, list):
            continue
        kept = [block for block in blocks if block.get("kind") != "section"]
        if len(kept) != len(blocks):
            bind.execute(table.update().where(table.c.id == row.id).values(blocks=kept))


def upgrade() -> None:
    bind = op.get_bind()
    _strip_sections(bind, "resume_versions")
    _strip_sections(bind, "tailoring_sessions")


def downgrade() -> None:
    pass