"""SQL 取数依据的展示文本；输出不作为数据库执行入口。"""

import re
from datetime import date
from decimal import Decimal

import sqlglot

from ..semantic import DIMENSIONS, METRICS, MasterDataPlan
from .compiler import MASTER_DATA


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
    return sqlglot.parse_one(rendered, read="postgres").sql(
        dialect="postgres", pretty=True
    )


BUSINESS_FACTS = {
    "revenue": (
        "收入确认流水 JOIN 合同明细 JOIN 合同台账",
        "确认日期",
        "SUM(不含税确认收入)",
    ),
    "signed": ("合同明细 JOIN 合同台账", "签约日期", "SUM(不含税签约金额)"),
    "payments": ("回款流水 JOIN 合同台账", "回款日期", "SUM(不含税回款金额)"),
    "cost": (
        "成本确认流水 JOIN 合同明细 JOIN 合同台账",
        "成本确认日期",
        "SUM(直接成本金额)",
    ),
    "floor": ("月度经营目标", "目标月份", "SUM(保底收入)"),
    "forecast": ("月度经营目标", "目标月份", "SUM(滚动预测收入)"),
    "outstanding_receivables": (
        "合同应收计划 JOIN 合同台账",
        "应收到期日",
        "SUM(应收金额-已核销金额)",
    ),
    "overdue_receivables": (
        "合同应收计划 JOIN 合同台账",
        "应收到期日",
        "SUM(逾期应收余额)",
    ),
}


def render_business_sql(plan):
    """生成帮助业务人员理解口径的中文 SQL；该文本仅用于解释。"""
    if isinstance(plan, MasterDataPlan):
        spec = MASTER_DATA[plan.entity]
        fields = ", ".join(label for _, label, _ in spec["columns"])
        conditions = []
        for item in plan.filters:
            values = ", ".join(
                "'" + value.replace("'", "''") + "'" for value in item.values
            )
            conditions.append(f"{DIMENSIONS[item.dimension]} IN ({values})")
        if plan.intent == "count":
            lines = [
                f"SELECT COUNT(*) AS {spec['name']}数量",
                f"FROM {spec['name']}基础资料",
            ]
        else:
            lines = [
                f"SELECT {fields}, COUNT(*) OVER() AS {spec['name']}总数",
                f"FROM {spec['name']}基础资料",
            ]
        if conditions:
            lines.append("WHERE " + " AND ".join(conditions))
        if plan.intent != "count":
            lines.extend(
                [
                    f"ORDER BY {spec['name']}编码 {'ASC' if plan.sort == 'asc' else 'DESC'}",
                    f"LIMIT {plan.limit}",
                ]
            )
        return "\n".join(lines) + ";"
    if plan.metric in {"gross_profit", "gross_margin"}:
        source, date_field = (
            "收入确认流水 JOIN 成本确认流水 JOIN 合同明细 JOIN 合同台账",
            "确认日期",
        )
        expression = "SUM(确认收入)-SUM(直接成本)"
        if plan.metric == "gross_margin":
            expression = "(SUM(确认收入)-SUM(直接成本))/NULLIF(SUM(确认收入),0)*100"
    elif plan.metric == "attainment":
        source, date_field = "收入确认流水 JOIN 月度经营目标", "月份"
        expression = "SUM(确认收入)/NULLIF(SUM(收入目标),0)*100"
    else:
        source, date_field, expression = BUSINESS_FACTS[plan.metric]
    dimensions = [DIMENSIONS[d] for d in plan.dimensions]
    select = ", ".join([*dimensions, f"{expression} AS {METRICS[plan.metric]['name']}"])
    conditions = [
        f"{date_field} >= '{plan.start_date}'",
        f"{date_field} <= '{plan.end_date}'",
    ]
    for item in plan.filters:
        values = ", ".join(
            "'" + value.replace("'", "''") + "'" for value in item.values
        )
        conditions.append(f"{DIMENSIONS[item.dimension]} IN ({values})")
    lines = [f"SELECT {select}", f"FROM {source}", "WHERE " + " AND ".join(conditions)]
    if dimensions:
        lines.append("GROUP BY " + ", ".join(dimensions))
        lines.append(
            f"ORDER BY {METRICS[plan.metric]['name']} {'DESC' if plan.sort == 'desc' else 'ASC'}"
        )
    lines.append(f"LIMIT {plan.limit}")
    return "\n".join(lines) + ";"
