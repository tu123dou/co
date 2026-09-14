"""日期对齐与 Decimal 指标计算；不依赖数据库和 HTTP。"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from .compiler import FACT_KEYS


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
    v = {k: Decimal(str(row.get(k) or 0)) for k in FACT_KEYS}
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
