from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from .semantic import METRICS
from .config import settings

FIELDS = {
    "region": "o.region",
    "city": "o.city",
    "org_unit": "o.name",
    "industry": "i.name",
    "customer": "c.name",
    "product_line": "p.name",
    "salesperson": "s.name",
}
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
}


def validate_sql(sql):
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
    }
    for f in tree.find_all(exp.Func):
        name = f.name.upper() if isinstance(f, exp.Anonymous) else f.sql_name().upper()
        if name not in allowed_funcs:
            raise ValueError("不允许的 SQL 函数: " + name)
    return sql


def fact_sql(fact, plan, params):
    if fact == "target":
        source = "analytics.monthly_targets f JOIN analytics.org_units o ON o.id=f.org_unit_id JOIN analytics.product_lines p ON p.id=f.product_line_id"
        dt = "f.month"
        amount = "f.revenue_target"
    else:
        if fact == "signed":
            source = "analytics.contract_items ci JOIN analytics.contracts ct ON ct.id=ci.contract_id"
            dt = "ct.signed_date"
            amount = "ci.amount_ex_tax"
        elif fact == "payments":
            source = "analytics.payment_entries f JOIN analytics.contracts ct ON ct.id=f.contract_id"
            dt = "f.payment_date"
            amount = "f.amount_ex_tax"
        else:
            tbl, col = (
                ("revenue_entries", "recognition_date")
                if fact == "revenue"
                else ("cost_entries", "cost_date")
            )
            source = f"analytics.{tbl} f JOIN analytics.contract_items ci ON ci.id=f.contract_item_id JOIN analytics.contracts ct ON ct.id=ci.contract_id"
            dt = f"f.{col}"
            amount = "f.amount_ex_tax"
        source += " JOIN analytics.org_units o ON o.id=ct.org_unit_id JOIN analytics.customers c ON c.id=ct.customer_id JOIN analytics.industries i ON i.id=c.industry_id JOIN analytics.salespeople s ON s.id=ct.salesperson_id"
        if fact != "payments":
            source += " JOIN analytics.products pr ON pr.id=ci.product_id JOIN analytics.product_lines p ON p.id=pr.product_line_id"

    def field(dim):
        return f"TO_CHAR({dt}, 'YYYY-MM')" if dim == "month" else FIELDS[dim]

    groups = [field(d) for d in plan.dimensions]
    cols = [f"{g} AS d{n}" for n, g in enumerate(groups)]
    cols += [
        f"{amount if key == fact else '0'} AS {key}"
        for key in ["revenue", "signed", "payments", "cost", "target"]
    ]
    where = [f"{dt} >= :start_date", f"{dt} <= :end_date"]
    if fact != "target":
        where.append("ct.status != 'cancelled'")
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
    params = {"start_date": plan.start_date, "end_date": plan.end_date}
    unions = " UNION ALL ".join(
        fact_sql(f, plan, params) for f in METRICS[plan.metric]["facts"]
    )
    group_cols = [f"d{n}" for n in range(len(plan.dimensions))]
    sums = ", ".join(
        f"SUM({m}) AS {m}" for m in ["revenue", "signed", "payments", "cost", "target"]
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


def previous_dates(plan):
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
    v = {
        k: Decimal(str(row.get(k) or 0))
        for k in ["revenue", "signed", "payments", "cost", "target"]
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
                conn.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": str(settings().query_timeout_ms)},
                )
                rows = [dict(r) for r in conn.execute(text(sql), params).mappings()]
        if len(rows) > 500:
            raise ValueError("分组超过500组，请缩小范围或改用区域、产品线分组")
        runs.append({"sql": sql, "parameters": {k: str(v) for k, v in params.items()}})
        return rows

    current = run(plan)
    previous = []
    if plan.comparison != "none":
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
        return value_of(
            {
                k: sum(Decimal(str(r.get(k) or 0)) for r in rs)
                for k in ["revenue", "signed", "payments", "cost", "target"]
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
                for k in ["revenue", "signed", "payments", "cost", "target"]
            )
            for r in current
        ),
        "executions": runs,
        "comparison_range": {"start": str(a), "end": str(b)}
        if previous or plan.comparison != "none"
        else None,
    }
