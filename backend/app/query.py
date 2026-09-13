"""受控 SQL 查询引擎。

输入不是大模型随意生成的 SQL，而是 semantic.py 定义的 Plan。这里根据指标选择
事实表，根据维度补齐关联表，再生成参数化 PostgreSQL 查询。SQL 会经过 SQLGlot
检查，并由数据库中的 analyst 只读账号执行，形成应用和数据库两层安全边界。
"""

from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal
import re
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from .semantic import METRICS, MasterDataPlan
from .config import settings

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
# FIELDS 把模型认识的逻辑维度映射到 SQL 字段。例如 customer 最终使用
# customers.name；合同和应收计划则拼成适合前端直接展示的唯一标签。
# 每个事实查询输出相同列结构，便于把不同来源安全地 UNION 后聚合。
FACT_KEYS = ["revenue", "signed", "payments", "cost", "target", "floor", "forecast", "outstanding_receivables", "overdue_receivables"]
# 即使 SQL 来自固定模板，仍使用白名单和 SQLGlot 做第二层安全校验。
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


# 主数据查询使用固定表、固定展示字段和有限的筛选映射，不允许模型提供物理字段。
MASTER_DATA = {
    "customer": {
        "name": "客户", "source": "analytics.customers m LEFT JOIN analytics.industries i ON i.id=m.industry_id",
        "columns": [("code", "客户编码", "m.code"), ("name", "客户名称", "m.name"), ("province", "省份", "m.province"), ("industry", "所属行业", "i.name")],
        "filters": {"industry": "i.name"},
    },
    "salesperson": {
        "name": "销售人员", "source": "analytics.salespeople m JOIN analytics.org_units o ON o.id=m.org_unit_id",
        "columns": [("code", "人员编码", "m.code"), ("name", "销售人员", "m.name"), ("org_unit", "所属经营单元", "o.name"), ("region", "区域", "o.region"), ("city", "城市", "o.city")],
        "filters": {"org_unit": "o.name", "region": "o.region", "city": "o.city"},
    },
    "product": {
        "name": "产品", "source": "analytics.products m JOIN analytics.product_lines p ON p.id=m.product_line_id",
        "columns": [("code", "产品编码", "m.code"), ("name", "产品名称", "m.name"), ("model", "产品型号", "m.model"), ("product_line", "所属产品线", "p.name")],
        "filters": {"product_line": "p.name"},
    },
    "product_line": {
        "name": "产品线", "source": "analytics.product_lines m",
        "columns": [("code", "产品线编码", "m.code"), ("name", "产品线名称", "m.name")], "filters": {},
    },
    "org_unit": {
        "name": "经营单元", "source": "analytics.org_units m",
        "columns": [("code", "经营单元编码", "m.code"), ("name", "经营单元", "m.name"), ("unit_type", "类型", "m.unit_type"), ("region", "区域", "m.region"), ("city", "城市", "m.city")],
        "filters": {"region": "m.region", "city": "m.city"},
    },
    "industry": {
        "name": "行业", "source": "analytics.industries m",
        "columns": [("code", "行业编码", "m.code"), ("name", "行业名称", "m.name")], "filters": {},
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
        where.append(f"{spec['filters'][item.dimension]} IN ({', '.join(placeholders)})")
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
        amount = {"target": "f.revenue_target", "floor": "f.floor_amount", "forecast": "f.forecast_amount"}[fact]
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
    cols += [
        f"{amount if key == fact else '0'} AS {key}"
        for key in FACT_KEYS
    ]
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
    sums = ", ".join(
        f"SUM({m}) AS {m}" for m in FACT_KEYS
    )
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


def render_executable_sql(sql, params):
    """把参数安全替换为 SQL 字面量，生成可直接粘贴到 DBeaver 的查询。"""
    def literal(value):
        if isinstance(value, date):
            return f"DATE '{value.isoformat()}'"
        if isinstance(value, (int, float, Decimal)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    rendered = sql
    # 参数名按长度倒序处理，避免 :f1 被误替换到 :f10 中。
    for name in sorted(params, key=len, reverse=True):
        rendered = re.sub(rf":{re.escape(name)}\b", literal(params[name]), rendered)
    return sqlglot.parse_one(rendered, read="postgres").sql(dialect="postgres", pretty=True)


BUSINESS_FACTS = {
    "revenue": ("收入确认流水 JOIN 合同明细 JOIN 合同台账", "确认日期", "SUM(不含税确认收入)"),
    "signed": ("合同明细 JOIN 合同台账", "签约日期", "SUM(不含税签约金额)"),
    "payments": ("回款流水 JOIN 合同台账", "回款日期", "SUM(不含税回款金额)"),
    "cost": ("成本确认流水 JOIN 合同明细 JOIN 合同台账", "成本确认日期", "SUM(直接成本金额)"),
    "floor": ("月度经营目标", "目标月份", "SUM(保底收入)"),
    "forecast": ("月度经营目标", "目标月份", "SUM(滚动预测收入)"),
    "outstanding_receivables": ("合同应收计划 JOIN 合同台账", "应收到期日", "SUM(应收金额-已核销金额)"),
    "overdue_receivables": ("合同应收计划 JOIN 合同台账", "应收到期日", "SUM(逾期应收余额)"),
}
BUSINESS_DIMENSIONS = {
    "region": "区域", "city": "城市", "org_unit": "经营单元", "industry": "行业",
    "customer": "客户", "product_line": "产品线", "salesperson": "销售人员",
    "contract": "合同", "receivable_plan": "应收计划", "month": "月份",
}


def render_business_sql(plan):
    """生成帮助业务人员理解口径的中文 SQL；该文本仅用于解释。"""
    if isinstance(plan, MasterDataPlan):
        spec = MASTER_DATA[plan.entity]
        fields = ", ".join(label for _, label, _ in spec["columns"])
        conditions = []
        for item in plan.filters:
            values = ", ".join("'" + value.replace("'", "''") + "'" for value in item.values)
            conditions.append(f"{BUSINESS_DIMENSIONS[item.dimension]} IN ({values})")
        if plan.intent == "count":
            lines = [f"SELECT COUNT(*) AS {spec['name']}数量", f"FROM {spec['name']}基础资料"]
        else:
            lines = [f"SELECT {fields}, COUNT(*) OVER() AS {spec['name']}总数", f"FROM {spec['name']}基础资料"]
        if conditions:
            lines.append("WHERE " + " AND ".join(conditions))
        if plan.intent != "count":
            lines.extend([f"ORDER BY {spec['name']}编码 {'ASC' if plan.sort == 'asc' else 'DESC'}", f"LIMIT {plan.limit}"])
        return "\n".join(lines) + ";"
    if plan.metric in {"gross_profit", "gross_margin"}:
        source, date_field = "收入确认流水 JOIN 成本确认流水 JOIN 合同明细 JOIN 合同台账", "确认日期"
        expression = "SUM(确认收入)-SUM(直接成本)"
        if plan.metric == "gross_margin":
            expression = "(SUM(确认收入)-SUM(直接成本))/NULLIF(SUM(确认收入),0)*100"
    elif plan.metric == "attainment":
        source, date_field = "收入确认流水 JOIN 月度经营目标", "月份"
        expression = "SUM(确认收入)/NULLIF(SUM(收入目标),0)*100"
    else:
        source, date_field, expression = BUSINESS_FACTS[plan.metric]
    dimensions = [BUSINESS_DIMENSIONS[d] for d in plan.dimensions]
    select = ", ".join([*dimensions, f"{expression} AS {METRICS[plan.metric]['name']}"])
    conditions = [
        f"{date_field} >= '{plan.start_date}'",
        f"{date_field} <= '{plan.end_date}'",
    ]
    for item in plan.filters:
        values = ", ".join("'" + value.replace("'", "''") + "'" for value in item.values)
        conditions.append(f"{BUSINESS_DIMENSIONS[item.dimension]} IN ({values})")
    lines = [f"SELECT {select}", f"FROM {source}", "WHERE " + " AND ".join(conditions)]
    if dimensions:
        lines.append("GROUP BY " + ", ".join(dimensions))
        lines.append(f"ORDER BY {METRICS[plan.metric]['name']} {'DESC' if plan.sort == 'desc' else 'ASC'}")
    lines.append(f"LIMIT {plan.limit}")
    return "\n".join(lines) + ";"


def previous_dates(plan):
    """计算同比或环比区间，并保持完整自然月口径。"""
    if plan.comparison == "yoy":

        def prior(d):
            return date(
                d.year - 1, d.month, min(d.day, monthrange(d.year - 1, d.month)[1])
            )

        return prior(plan.start_date), prior(plan.end_date)
    if (
        plan.start_date.day == 1
        and plan.end_date.day == monthrange(plan.end_date.year, plan.end_date.month)[1]
    ):
        months = (
            (plan.end_date.year - plan.start_date.year) * 12
            + plan.end_date.month
            - plan.start_date.month
            + 1
        )
        idx = plan.start_date.year * 12 + plan.start_date.month - 1 - months
        return date(idx // 12, idx % 12 + 1, 1), plan.start_date - timedelta(days=1)
    return plan.start_date - (plan.end_date - plan.start_date) - timedelta(
        days=1
    ), plan.start_date - timedelta(days=1)


def value_of(row, metric):
    """先聚合基础事实，再计算毛利率、达成率等派生指标。"""
    v = {
        k: Decimal(str(row.get(k) or 0))
        for k in FACT_KEYS
    }
    if metric == "gross_profit":
        return float(v["revenue"] - v["cost"])
    if metric == "gross_margin":
        return (
            float((v["revenue"] - v["cost"]) / v["revenue"] * 100)
            if v["revenue"]
            else None
        )
    if metric == "attainment":
        return float(v["revenue"] / v["target"] * 100) if v["target"] else None
    return float(v[metric])


def execute_plan(plan, query_engine, cutoff, start):
    """只读执行当前期和对比期计划，并整理为接口需要的结果结构。"""
    if isinstance(plan, MasterDataPlan):
        sql, params = compile_plan(plan)
        with query_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(text("SELECT set_config('statement_timeout', :timeout, true)"), {"timeout": str(settings().query_timeout_ms)})
                records = [dict(row) for row in conn.execute(text(sql), params).mappings()]
        total_count = int(records[0].pop("total_count")) if records else 0
        if plan.intent == "count":
            records = []
        spec = MASTER_DATA[plan.entity]
        execution = {"sql": sql, "executable_sql": render_executable_sql(sql, params), "business_sql": render_business_sql(plan), "parameters": {k: str(v) for k, v in params.items()}}
        return {
            "records": records, "record_columns": [{"key": key, "title": title} for key, title, _ in spec["columns"]],
            "total_count": total_count, "rows": [], "group_count": total_count,
            "truncated": plan.intent != "count" and total_count > len(records), "empty": total_count == 0,
            "executions": [execution], "previous_total": None, "comparison_range": None,
        }
    if plan.start_date < start or plan.end_date > cutoff:
        raise ValueError(f"数据覆盖 {start} 至 {cutoff}，请调整查询时间")
    if plan.comparison != "none":
        a, b = previous_dates(plan)
        if a < start:
            raise ValueError("对比期间超出数据覆盖范围，无法提供完整同比或环比")
    runs = []

    def run(p):
        sql, params = compile_plan(p)
        with query_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                # 数据库级超时限制异常宽泛查询对服务的影响。
                conn.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": str(settings().query_timeout_ms)},
                )
                rows = [dict(r) for r in conn.execute(text(sql), params).mappings()]
        if len(rows) > 500:
            raise ValueError("分组超过500组，请缩小范围或改用区域、产品线分组")
        runs.append({
            "sql": sql,
            "executable_sql": render_executable_sql(sql, params),
            "business_sql": render_business_sql(p),
            "parameters": {k: str(v) for k, v in params.items()},
        })
        return rows

    current = run(plan)
    previous = []
    if plan.comparison != "none":
        # 对比查询复用同一份计划，只替换日期以及可能存在的月份筛选值。
        offset = (plan.start_date.year - a.year) * 12 + plan.start_date.month - a.month
        previous_filters = []
        for f in plan.filters:
            if f.dimension == "month":
                values = []
                for value in f.values:
                    year, month = map(int, value.split("-"))
                    idx = year * 12 + month - 1 - offset
                    values.append(f"{idx // 12:04d}-{idx % 12 + 1:02d}")
                previous_filters.append(f.model_copy(update={"values": values}))
            else:
                previous_filters.append(f)
        previous = run(
            plan.model_copy(
                update={"start_date": a, "end_date": b, "filters": previous_filters}
            )
        )
    if plan.comparison != "none" and "month" in plan.dimensions:
        month_col = "d" + str(plan.dimensions.index("month"))
        offset = (plan.start_date.year - a.year) * 12 + plan.start_date.month - a.month
        for r in previous:
            y, m = map(int, r[month_col].split("-"))
            idx = y * 12 + m - 1 + offset
            r[month_col] = f"{idx // 12:04d}-{idx % 12 + 1:02d}"

    def key(r):
        # 维度值组成行键，用于把当前期和对比期的同一分组对齐。
        return tuple(r[f"d{i}"] for i in range(len(plan.dimensions)))

    cur = {key(r): r for r in current}
    prev = {key(r): r for r in previous}
    rows = []
    for k in cur.keys() | prev.keys():
        v = value_of(cur.get(k, {}), plan.metric)
        old = (
            value_of(prev.get(k, {}), plan.metric)
            if plan.comparison != "none"
            else None
        )
        delta = (v - old) if v is not None and old is not None else None
        change = (delta / abs(old) * 100) if delta is not None and old else None
        rows.append(
            {
                "label": " / ".join(k) if k else "全部",
                "dimensions": dict(zip(plan.dimensions, k)),
                "value": v,
                "previous": old,
                "change": change,
                "difference": delta,
            }
        )
    if "month" in plan.dimensions:
        rows.sort(
            key=lambda r: tuple(r["dimensions"].get(d, "") for d in plan.dimensions)
        )
    else:
        rows.sort(
            key=lambda r: (
                r["value"] is None,
                -(r["value"] or 0) if plan.sort == "desc" else (r["value"] or 0),
                r["label"],
            )
        )

    def total(rs):
        # 总计从未截断的原始分组重新计算，不能只累加前端展示的前 N 行。
        return value_of(
            {
                k: sum(Decimal(str(r.get(k) or 0)) for r in rs)
                for k in FACT_KEYS
            },
            plan.metric,
        )

    allvalue = total(current)
    allprevious = total(previous) if plan.comparison != "none" else None
    total_diff = (
        allvalue - allprevious
        if allvalue is not None and allprevious is not None
        else None
    )
    return {
        "rows": rows[: plan.limit],
        "total": allvalue,
        "previous_total": allprevious,
        "difference": total_diff,
        "change": total_diff / abs(allprevious) * 100
        if total_diff is not None and allprevious
        else None,
        "group_count": len(rows),
        "truncated": len(rows) > plan.limit,
        "empty": not current
        or all(
            all(
                r[k] is None
                for k in FACT_KEYS
            )
            for r in current
        ),
        "executions": runs,
        "comparison_range": {"start": str(a), "end": str(b)}
        if previous or plan.comparison != "none"
        else None,
    }
