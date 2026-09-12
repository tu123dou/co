"""数据库说明迁移：为已有表和字段写入中文业务注释。

Revision ID: 0002
Revises: 0001
"""

from alembic import op
from app.catalog import TABLE_CATALOG
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# 迁移文件必须只处理当时已经存在的表。业务目录会持续增加新表，若在这里
# 直接遍历最新目录，全新部署会在后续迁移创建表之前执行 COMMENT 而失败。
INITIAL_TABLES = {
    "analytics.industries", "analytics.org_units", "analytics.product_lines",
    "analytics.customers", "analytics.monthly_targets", "analytics.products",
    "analytics.salespeople", "analytics.contracts", "analytics.contract_items",
    "analytics.payment_entries", "analytics.cost_entries", "analytics.revenue_entries",
    "app.dataset_versions", "app.metric_definitions", "app.users",
    "app.conversations", "app.favorite_questions", "app.messages",
    "app.feedbacks", "app.query_runs",
}
CATALOG = {
    name: spec for name, spec in TABLE_CATALOG.items() if name in INITIAL_TABLES
}
LATER_COLUMNS = {
    "analytics.org_units": {"code", "unit_type"}, "analytics.industries": {"code"},
    "analytics.customers": {"code", "customer_type", "province"}, "analytics.product_lines": {"code"},
    "analytics.products": {"code", "model"}, "analytics.salespeople": {"code"},
    "analytics.contracts": {"name", "opportunity_id", "end_customer_id"},
    "analytics.contract_items": {"quantity", "unit_name", "tax_rate", "amount_with_tax"},
    "analytics.monthly_targets": {"floor_amount", "forecast_amount"},
    "app.feedbacks": {"resolution_note", "updated_at"},
}


def _qualified(identifier: str) -> str:
    """Quote a catalog-controlled identifier; never accepts user input."""
    return ".".join(
        '"' + part.replace('"', '""') + '"' for part in identifier.split(".")
    )


def _set_comment(object_type: str, identifier: str, comment: str | None) -> None:
    # PostgreSQL's COMMENT statement does not accept a bind parameter in the
    # string-literal position. The catalog is trusted source code; escape SQL
    # string literals here while identifiers are quoted separately above.
    value = "NULL" if comment is None else "'" + comment.replace("'", "''") + "'"
    statement = text(f"COMMENT ON {object_type} {_qualified(identifier)} IS {value}")
    op.get_bind().execute(statement)


def upgrade():
    """按照业务目录写入表、字段及数据粒度说明。"""
    _set_comment(
        "SCHEMA",
        "analytics",
        "经营分析业务数据域；仅包含可供受控问数查询的模拟业务表。",
    )
    _set_comment(
        "SCHEMA",
        "app",
        "智能问数应用数据域；包含账号、会话、执行追溯和配置，不向问数账号开放。",
    )
    for table_name, spec in CATALOG.items():
        _set_comment("TABLE", table_name, spec["comment"])
        for column_name, comment in spec["columns"].items():
            if column_name in LATER_COLUMNS.get(table_name, set()):
                continue
            _set_comment("COLUMN", f"{table_name}.{column_name}", comment)
    # Alembic owns this infrastructure table, so it is documented separately
    # from the 20 product-domain tables in TABLE_CATALOG.
    _set_comment(
        "TABLE",
        "public.alembic_version",
        "数据库迁移版本表。用途：记录当前已应用的 Alembic 迁移版本。粒度：每行一个当前迁移版本标识；通常仅一行。",
    )
    _set_comment(
        "COLUMN",
        "public.alembic_version.version_num",
        "当前数据库已应用的最新 Alembic 迁移版本号。",
    )


def downgrade():
    """移除本版本写入的数据库对象注释。"""
    for table_name, spec in reversed(CATALOG.items()):
        for column_name in reversed(spec["columns"]):
            if column_name in LATER_COLUMNS.get(table_name, set()):
                continue
            _set_comment("COLUMN", f"{table_name}.{column_name}", None)
        _set_comment("TABLE", table_name, None)
    _set_comment("COLUMN", "public.alembic_version.version_num", None)
    _set_comment("TABLE", "public.alembic_version", None)
    _set_comment("SCHEMA", "analytics", None)
    _set_comment("SCHEMA", "app", None)
