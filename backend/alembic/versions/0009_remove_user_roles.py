"""移除未使用的管理员角色概念。

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    """所有工作台能力都按当前用户隔离，因此不再保存管理员或普通用户角色。"""
    op.execute(
        sa.text(
            "UPDATE app.users SET display_name='演示用户' "
            "WHERE username='admin' AND display_name='管理员'"
        )
    )
    op.drop_column("users", "role", schema="app")


def downgrade():
    """角色权限不会由自动回退重新推断。"""
    raise RuntimeError("User roles are restored only by a reviewed data migration.")
