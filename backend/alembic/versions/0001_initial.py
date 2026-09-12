"""初始迁移：创建第一版业务表和应用表，结构快照由本迁移固定保存。"""

from alembic import op
from sqlalchemy import text
from pathlib import Path

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """创建数据库模式，并执行初始结构 SQL。"""
    conn = op.get_bind()
    for statement in Path(__file__).with_suffix(".sql").read_text().split(";"):
        if statement.strip():
            conn.execute(text(statement))


def downgrade():
    """删除初始结构；仅用于明确的版本回退。"""
    raise RuntimeError(
        "Destructive rollback is disabled; restore a reviewed backup instead."
    )
