"""增加超管标识并隔离反馈数据。

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    """默认账号 admin 作为首位超管，其他现有和新增用户保持普通权限。"""
    op.add_column(
        "users",
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="app",
    )
    op.execute("UPDATE app.users SET is_superuser = true WHERE username = 'admin'")
    op.execute(
        "COMMENT ON COLUMN app.users.is_superuser IS "
        "'是否为系统超管；超管可以跨用户查看并处理回复反馈。'"
    )


def downgrade():
    """权限字段移除会改变访问边界，因此禁止自动回退。"""
    raise RuntimeError("Superuser permissions require a reviewed migration to remove.")
