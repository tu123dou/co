"""受控 SQL 执行、分组与对比结果组装。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..config import settings
from ..contracts import QueryPlan, QueryResult
from ..semantic import MasterDataPlan
from .calculations import previous_dates, value_of
from .compiler import FACT_KEYS, MASTER_DATA, compile_plan
from .display import render_business_sql, render_executable_sql


def execute_plan(
    plan: QueryPlan, query_engine: Engine, cutoff: date, start: date
) -> QueryResult:
    """只读执行当前期和对比期计划，并整理为接口需要的结果结构。"""
    if isinstance(plan, MasterDataPlan):
        sql, params = compile_plan(plan)
        with query_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": str(settings().query_timeout_ms)},
                )
                records = [
                    dict(row) for row in conn.execute(text(sql), params).mappings()
                ]
        total_count = int(records[0].pop("total_count")) if records else 0
        if plan.intent == "count":
            records = []
        spec = MASTER_DATA[plan.entity]
        execution = {
            "sql": sql,
            "executable_sql": render_executable_sql(sql, params),
            "business_sql": render_business_sql(plan),
            "parameters": {k: str(v) for k, v in params.items()},
        }
        return {
            "records": records,
            "record_columns": [
                {"key": key, "title": title} for key, title, _ in spec["columns"]
            ],
            "total_count": total_count,
            "rows": [],
            "group_count": total_count,
            "truncated": plan.intent != "count" and total_count > len(records),
            "empty": total_count == 0,
            "executions": [execution],
            "previous_total": None,
            "comparison_range": None,
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
        runs.append(
            {
                "sql": sql,
                "executable_sql": render_executable_sql(sql, params),
                "business_sql": render_business_sql(p),
                "parameters": {k: str(v) for k, v in params.items()},
            }
        )
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
            {k: sum(Decimal(str(r.get(k) or 0)) for r in rs) for k in FACT_KEYS},
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
        or all(all(r[k] is None for k in FACT_KEYS) for r in current),
        "executions": runs,
        "comparison_range": {"start": str(a), "end": str(b)}
        if previous or plan.comparison != "none"
        else None,
    }
