"""客户模型简化迁移：合同只保留一个明确的 customer_id。

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    """迁移原终端客户值，并删除终端客户和客户类型概念。"""
    # Existing analytics used end_customer_id. Copy it into the surviving key
    # before removing the duplicate customer concept so results stay stable.
    op.execute(
        "UPDATE analytics.contracts "
        "SET customer_id=end_customer_id "
        "WHERE customer_id IS DISTINCT FROM end_customer_id"
    )
    op.drop_constraint(
        "contracts_end_customer_id_fkey",
        "contracts",
        schema="analytics",
        type_="foreignkey",
    )
    op.drop_column("contracts", "end_customer_id", schema="analytics")
    op.drop_column("customers", "customer_type", schema="analytics")


def downgrade():
    """恢复历史字段；无法自动还原已经合并前的客户关系。"""
    raise RuntimeError("Removed customer concepts are restored by reviewed data migration only.")
