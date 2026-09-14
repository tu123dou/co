"""受控计划编译与 AST 安全校验；不连接数据库。"""

import sqlglot
from sqlglot import exp

from ..semantic import METRICS, MasterDataPlan

FIELDS = {
    "region": "o.region",
    "city": "o.city",
    "org_unit": "o.name",
    "industry": "i.name",
    "customer": "c.name",
    "product_line": "p.name",
    "salesperson": "s.name",
    "contract": "ct.number || '｜' || ct.name",
    "receivable_plan": "ct.number || '｜' || ct.name || '｜' || TO_CHAR(f.due_date, 'YYYY-MM-DD') || '到期｜计划' || CAST(f.id AS TEXT)",
}


FACT_KEYS = [
    "revenue",
    "signed",
    "payments",
    "cost",
    "target",
    "floor",
    "forecast",
    "outstanding_receivables",
    "overdue_receivables",
]


ALLOWED_TABLES = {
    "org_units",
    "industries",
    "customers",
    "product_lines",
    "products",
    "salespeople",
    "contracts",
    "contract_items",
    "revenue_entries",
    "payment_entries",
    "cost_entries",
    "monthly_targets",
    "receivable_entries",
}


def validate_sql(sql):
    """只允许单条 SELECT，并限制其访问获准的 analytics 表和函数。"""
    trees = sqlglot.parse(sql, read="postgres")
    if len(trees) != 1 or not isinstance(trees[0], exp.Select):
        raise ValueError("仅允许单条只读查询")
    tree = trees[0]
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Command,
        exp.Into,
        exp.Copy,
        exp.Lock,
        exp.Merge,
        exp.Alter,
    )
    if any(isinstance(node, forbidden) for node in tree.walk()):
        raise ValueError("不允许的 SQL 操作")
    ctes = {node.alias for node in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if t.catalog or (
            t.name not in ctes and (t.db != "analytics" or t.name not in ALLOWED_TABLES)
        ):
            raise ValueError("不允许访问此数据表")
    allowed_funcs = {
        "SUM",
        "COALESCE",
        "NULLIF",
        "TO_CHAR",
        "TIME_TO_STR",
        "CAST",
        "AND",
        "OR",
        "COUNT",
    }
    for f in tree.find_all(exp.Func):
        name = f.name.upper() if isinstance(f, exp.Anonymous) else f.sql_name().upper()
        if name not in allowed_funcs:
            raise ValueError("不允许的 SQL 函数: " + name)
    return sql


MASTER_DATA = {
    "customer": {
        "name": "客户",
        "source": "analytics.customers m LEFT JOIN analytics.industries i ON i.id=m.industry_id",
        "columns": [
            ("code", "客户编码", "m.code"),
            ("name", "客户名称", "m.name"),
            ("province", "省份", "m.province"),
            ("industry", "所属行业", "i.name"),
        ],
        "filters": {"industry": "i.name"},
    },
    "salesperson": {
        "name": "销售人员",
        "source": "analytics.salespeople m JOIN analytics.org_units o ON o.id=m.org_unit_id",
        "columns": [
            ("code", "人员编码", "m.code"),
            ("name", "销售人员", "m.name"),
            ("org_unit", "所属经营单元", "o.name"),
            ("region", "区域", "o.region"),
            ("city", "城市", "o.city"),
        ],
        "filters": {"org_unit": "o.name", "region": "o.region", "city": "o.city"},
    },
    "product": {
        "name": "产品",
        "source": "analytics.products m JOIN analytics.product_lines p ON p.id=m.product_line_id",
        "columns": [
            ("code", "产品编码", "m.code"),
            ("name", "产品名称", "m.name"),
            ("model", "产品型号", "m.model"),
            ("product_line", "所属产品线", "p.name"),
        ],
        "filters": {"product_line": "p.name"},
    },
    "product_line": {
        "name": "产品线",
        "source": "analytics.product_lines m",
        "columns": [("code", "产品线编码", "m.code"), ("name", "产品线名称", "m.name")],
        "filters": {},
    },
    "org_unit": {
        "name": "经营单元",
        "source": "analytics.org_units m",
        "columns": [
            ("code", "经营单元编码", "m.code"),
            ("name", "经营单元", "m.name"),
            ("unit_type", "类型", "m.unit_type"),
            ("region", "区域", "m.region"),
            ("city", "城市", "m.city"),
        ],
        "filters": {"region": "m.region", "city": "m.city"},
    },
    "industry": {
        "name": "行业",
        "source": "analytics.industries m",
        "columns": [("code", "行业编码", "m.code"), ("name", "行业名称", "m.name")],
        "filters": {},
    },
}


def compile_master_data_plan(plan):
    spec = MASTER_DATA[plan.entity]
    params = {"limit": plan.limit}
    where = []
    for n, item in enumerate(plan.filters):
        placeholders = []
        for k, value in enumerate(item.values):
            key = f"f{n}_{k}"
            params[key] = value
            placeholders.append(":" + key)
        where.append(
            f"{spec['filters'][item.dimension]} IN ({', '.join(placeholders)})"
        )
    condition = " WHERE " + " AND ".join(where) if where else ""
    if plan.intent == "count":
        sql = f"SELECT COUNT(*) AS total_count FROM {spec['source']}{condition}"
    else:
        selected = ", ".join(f"{field} AS {key}" for key, _, field in spec["columns"])
        direction = "ASC" if plan.sort == "asc" else "DESC"
        sql = f"SELECT {selected}, COUNT(*) OVER() AS total_count FROM {spec['source']}{condition} ORDER BY m.code {direction} LIMIT :limit"
    return validate_sql(sql), params


def fact_sql(fact, plan, params):
    """把一个物理事实来源编译为统一的待聚合列结构。"""
    extra_where = []
    used_dimensions = set(plan.dimensions) | {item.dimension for item in plan.filters}
    needs_org = bool(used_dimensions & {"region", "city", "org_unit"})
    needs_customer = bool(used_dimensions & {"customer", "industry"})
    needs_industry = "industry" in used_dimensions
    needs_salesperson = "salesperson" in used_dimensions
    needs_product_line = "product_line" in used_dimensions

    def contract_dimensions(source):
        """只关联本次计划实际使用的合同归属维表。"""
        if needs_org:
            source += " JOIN analytics.org_units o ON o.id=ct.org_unit_id"
        if needs_customer:
            source += " JOIN analytics.customers c ON c.id=ct.customer_id"
        if needs_industry:
            source += " JOIN analytics.industries i ON i.id=c.industry_id"
        if needs_salesperson:
            source += " JOIN analytics.salespeople s ON s.id=ct.salesperson_id"
        return source

    if fact in {"target", "floor", "forecast"}:
        # 目标、保底和预测共用月度计划表，最细粒度是“月份+组织+产品线”。
        source = "analytics.monthly_targets f"
        if needs_org:
            source += " JOIN analytics.org_units o ON o.id=f.org_unit_id"
        if needs_product_line:
            source += " JOIN analytics.product_lines p ON p.id=f.product_line_id"
        dt = "f.month"
        amount = {
            "target": "f.revenue_target",
            "floor": "f.floor_amount",
            "forecast": "f.forecast_amount",
        }[fact]
    elif fact in {"outstanding_receivables", "overdue_receivables"}:
        # 应收事实位于合同层，通过合同再关联客户、组织和销售人员。
        source = contract_dimensions(
            "analytics.receivable_entries f JOIN analytics.contracts ct ON ct.id=f.contract_id"
        )
        dt = "f.due_date"
        amount = "f.amount_ex_tax - f.settled_amount_ex_tax"
        if fact == "overdue_receivables":
            extra_where.append("f.due_date < :cutoff_date")
            params["cutoff_date"] = plan.end_date
    else:
        if fact == "signed":
            # 签约额取合同明细金额，日期口径使用合同签约日期。
            source = "analytics.contract_items ci JOIN analytics.contracts ct ON ct.id=ci.contract_id"
            dt = "ct.signed_date"
            amount = "ci.amount_ex_tax"
        elif fact == "payments":
            # 回款记录只有合同归属，无法可靠拆分到具体产品线。
            source = "analytics.payment_entries f JOIN analytics.contracts ct ON ct.id=f.contract_id"
            dt = "f.payment_date"
            amount = "f.amount_ex_tax"
        else:
            # 收入和成本都落到合同明细，因此可以继续关联具体产品及产品线。
            tbl, col = (
                ("revenue_entries", "recognition_date")
                if fact == "revenue"
                else ("cost_entries", "cost_date")
            )
            source = f"analytics.{tbl} f JOIN analytics.contract_items ci ON ci.id=f.contract_item_id JOIN analytics.contracts ct ON ct.id=ci.contract_id"
            dt = f"f.{col}"
            amount = "f.amount_ex_tax"
        source = contract_dimensions(source)
        if fact != "payments" and needs_product_line:
            source += " JOIN analytics.products pr ON pr.id=ci.product_id JOIN analytics.product_lines p ON p.id=pr.product_line_id"

    def field(dim):
        # 将逻辑维度解析成当前事实查询已经关联的物理字段。
        return f"TO_CHAR({dt}, 'YYYY-MM')" if dim == "month" else FIELDS[dim]

    groups = [field(d) for d in plan.dimensions]
    cols = [f"{g} AS d{n}" for n, g in enumerate(groups)]
    cols += [f"{amount if key == fact else '0'} AS {key}" for key in FACT_KEYS]
    where = [f"{dt} >= :start_date", f"{dt} <= :end_date"]
    if fact != "target":
        if fact not in {"floor", "forecast"}:
            where.append("ct.status != 'cancelled'")
    where.extend(extra_where)
    for n, f in enumerate(plan.filters):
        placeholders = []
        for k, value in enumerate(f.values):
            name = f"f{n}_{k}"
            params[name] = value
            placeholders.append(":" + name)
        where.append(f"{field(f.dimension)} IN ({', '.join(placeholders)})")
    return (
        "SELECT "
        + ", ".join(cols)
        + " FROM "
        + source
        + " WHERE "
        + " AND ".join(where)
    )


def compile_plan(plan):
    """编译已校验的计划；用户和模型给出的值始终通过参数绑定。"""
    if isinstance(plan, MasterDataPlan):
        return compile_master_data_plan(plan)
    params = {"start_date": plan.start_date, "end_date": plan.end_date}
    unions = " UNION ALL ".join(
        fact_sql(f, plan, params) for f in METRICS[plan.metric]["facts"]
    )
    group_cols = [f"d{n}" for n in range(len(plan.dimensions))]
    sums = ", ".join(f"SUM({m}) AS {m}" for m in FACT_KEYS)
    groups = ", ".join(group_cols)
    sql = (
        f"WITH facts AS ({unions}) SELECT "
        + (groups + ", " if groups else "")
        + sums
        + " FROM facts"
        + (" GROUP BY " + groups if groups else "")
        + " LIMIT 501"
    )
    return validate_sql(sql), params
