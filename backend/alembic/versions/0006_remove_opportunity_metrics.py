"""指标清理迁移：删除依赖已移除商机域的指标定义。

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    """移除管道金额和高风险项目等失效指标。"""
    op.get_bind().execute(
        sa.text(
            "DELETE FROM app.metric_definitions "
            "WHERE code IN ('pipeline', 'weighted_pipeline', 'high_risk_projects')"
        )
    )


def downgrade():
    """恢复历史商机指标定义，供数据库版本回退。"""
    raise RuntimeError("Removed metric definitions are restored by reviewed data migration only.")
