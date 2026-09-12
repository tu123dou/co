"""业务域迁移：把基础销售模型调整为算力基础设施项目业务结构。"""

from alembic import op
import sqlalchemy as sa
from app.catalog import TABLE_CATALOG

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _add_code(table, prefix):
    op.add_column(table, sa.Column("code", sa.String(50), nullable=True), schema="analytics")
    op.execute(sa.text(f"UPDATE analytics.{table} SET code=:prefix || lpad(id::text, 5, '0')").bindparams(prefix=prefix))
    op.alter_column(table, "code", nullable=False, schema="analytics")
    op.create_unique_constraint(f"uq_{table}_code", table, ["code"], schema="analytics")


def _comment_all():
    conn = op.get_bind()
    for full_name, spec in TABLE_CATALOG.items():
        if not full_name.startswith("analytics."):
            continue
        schema, table = full_name.split(".")
        value = spec["comment"].replace("'", "''")
        conn.execute(sa.text(f'COMMENT ON TABLE "{schema}"."{table}" IS \'{value}\''))
        for column, comment in spec["columns"].items():
            value = comment.replace("'", "''")
            conn.execute(sa.text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS \'{value}\''))


def upgrade():
    """增加产品、组织、合同、预测和应收等业务字段与表。"""
    for table, prefix in [
        ("org_units", "OU-"), ("industries", "IND-"), ("customers", "CUS-"),
        ("product_lines", "PL-"), ("products", "PRD-"), ("salespeople", "EMP-"),
    ]:
        _add_code(table, prefix)

    op.add_column("org_units", sa.Column("unit_type", sa.String(30), server_default="代表处", nullable=False), schema="analytics")
    op.alter_column("org_units", "region", nullable=True, schema="analytics")
    op.alter_column("org_units", "city", nullable=True, schema="analytics")
    op.add_column("customers", sa.Column("customer_type", sa.String(30), server_default="最终客户", nullable=False), schema="analytics")
    op.add_column("customers", sa.Column("province", sa.String(30)), schema="analytics")
    op.add_column("products", sa.Column("model", sa.String(80), server_default="未定义型号", nullable=False), schema="analytics")

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("analytics.customers.id"), nullable=False),
        sa.Column("end_customer_id", sa.Integer(), sa.ForeignKey("analytics.customers.id"), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), sa.ForeignKey("analytics.org_units.id"), nullable=False),
        sa.Column("salesperson_id", sa.Integer(), sa.ForeignKey("analytics.salespeople.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("analytics.products.id"), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_amount_ex_tax", sa.Numeric(18, 2), nullable=False),
        sa.Column("win_probability", sa.Numeric(5, 4), nullable=False),
        sa.Column("tender_date", sa.Date()), sa.Column("expected_sign_date", sa.Date()),
        sa.Column("planned_delivery_date", sa.Date()), sa.Column("actual_delivery_date", sa.Date()),
        sa.Column("planned_acceptance_date", sa.Date()), sa.Column("actual_acceptance_date", sa.Date()),
        sa.Column("risk_level", sa.String(20), nullable=False), sa.Column("risk_type", sa.String(30)), sa.Column("risk_note", sa.Text()),
        sa.CheckConstraint("expected_quantity > 0"), sa.CheckConstraint("expected_amount_ex_tax >= 0"),
        sa.CheckConstraint("win_probability >= 0 AND win_probability <= 1"),
        schema="analytics",
    )
    op.create_index("ix_opportunities_expected_sign_date_stage", "opportunities", ["expected_sign_date", "stage"], schema="analytics")
    op.create_index("ix_opportunities_risk_level", "opportunities", ["risk_level"], schema="analytics")

    op.add_column("contracts", sa.Column("name", sa.String(160)), schema="analytics")
    op.add_column("contracts", sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("analytics.opportunities.id")), schema="analytics")
    op.add_column("contracts", sa.Column("end_customer_id", sa.Integer(), sa.ForeignKey("analytics.customers.id")), schema="analytics")
    op.execute("UPDATE analytics.contracts SET name='算力产品采购合同-' || number, end_customer_id=customer_id")
    op.alter_column("contracts", "name", nullable=False, schema="analytics")
    op.alter_column("contracts", "end_customer_id", nullable=False, schema="analytics")

    for name, column in [
        ("quantity", sa.Column("quantity", sa.Numeric(12, 2))),
        ("unit_name", sa.Column("unit_name", sa.String(20))),
        ("tax_rate", sa.Column("tax_rate", sa.Numeric(6, 4))),
        ("amount_with_tax", sa.Column("amount_with_tax", sa.Numeric(18, 2))),
    ]:
        op.add_column("contract_items", column, schema="analytics")
    op.execute("UPDATE analytics.contract_items SET quantity=1, unit_name='套', tax_rate=0.13, amount_with_tax=round(amount_ex_tax*1.13,2)")
    for name in ["quantity", "unit_name", "tax_rate", "amount_with_tax"]:
        op.alter_column("contract_items", name, nullable=False, schema="analytics")
    op.create_check_constraint("ck_contract_items_quantity", "contract_items", "quantity > 0", schema="analytics")
    op.create_check_constraint("ck_contract_items_tax_rate", "contract_items", "tax_rate >= 0", schema="analytics")

    op.add_column("monthly_targets", sa.Column("floor_amount", sa.Numeric(18, 2)), schema="analytics")
    op.add_column("monthly_targets", sa.Column("forecast_amount", sa.Numeric(18, 2)), schema="analytics")
    op.execute("UPDATE analytics.monthly_targets SET floor_amount=revenue_target*0.82, forecast_amount=revenue_target*0.94")
    for name in ["floor_amount", "forecast_amount"]:
        op.alter_column("monthly_targets", name, nullable=False, schema="analytics")
        op.create_check_constraint(f"ck_monthly_targets_{name}", "monthly_targets", f"{name} >= 0", schema="analytics")

    op.create_table(
        "receivable_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("analytics.contracts.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_ex_tax", sa.Numeric(18, 2), nullable=False),
        sa.Column("settled_amount_ex_tax", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("amount_ex_tax >= 0"), sa.CheckConstraint("settled_amount_ex_tax >= 0"),
        sa.CheckConstraint("settled_amount_ex_tax <= amount_ex_tax"),
        schema="analytics",
    )
    op.create_index("ix_receivable_entries_due_date_contract_id", "receivable_entries", ["due_date", "contract_id"], schema="analytics")
    _comment_all()


def downgrade():
    """将数据库结构回退到通用销售业务模型。"""
    raise RuntimeError("Destructive rollback is disabled; restore a reviewed backup instead.")
