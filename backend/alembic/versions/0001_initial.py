"""Initial domain schema. Schema snapshot is frozen in this revision's companion."""

from alembic import op
from sqlalchemy import text
from pathlib import Path

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for statement in Path(__file__).with_suffix(".sql").read_text().split(";"):
        if statement.strip():
            conn.execute(text(statement))


def downgrade():
    raise RuntimeError(
        "Destructive rollback is disabled; restore a reviewed backup instead."
    )
