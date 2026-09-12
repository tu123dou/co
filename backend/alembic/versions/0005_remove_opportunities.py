"""业务简化迁移：删除非核心的售前商机表及合同关联字段。

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    """解除合同关联并删除 opportunities 表。"""
    op.drop_constraint(
        "contracts_opportunity_id_fkey",
        "contracts",
        schema="analytics",
        type_="foreignkey",
    )
    op.drop_column("contracts", "opportunity_id", schema="analytics")
    op.drop_table("opportunities", schema="analytics")


def downgrade():
    """恢复历史商机表结构及合同关联字段。"""
    raise RuntimeError("Destructive rollback is disabled; restore a reviewed backup instead.")
