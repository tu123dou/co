"""问数系统的业务语义契约。

METRICS 定义“算什么”，DIMENSIONS 定义“按什么查看”。大模型只能输出这里声明的
Plan，不能自行增加表名或字段名。Pydantic 会检查日期、筛选、指标与维度组合，
通过后才交给 query.py 编译 SQL。
"""

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

METRICS = {
    # facts 表示计算指标所需的基础事实。普通指标通常只有一个事实，毛利等派生指标
    # 会先分别查询多个事实，再在 query.py 中按统一维度计算。
    "revenue": {
        "name": "确认收入",
        "unit": "元",
        "definition": "按收入确认日期汇总不含税金额；不等同于签约额或回款额。",
        "facts": ["revenue"],
    },
    "signed": {
        "name": "签约额",
        "unit": "元",
        "definition": "按合同签约日期汇总有效合同明细的不含税签约金额。",
        "facts": ["signed"],
    },
    "payments": {
        "name": "回款额",
        "unit": "元",
        "definition": "按回款日期汇总合同回款的不含税管理折算金额；不支持产品线拆分。",
        "facts": ["payments"],
    },
    "cost": {
        "name": "直接成本",
        "unit": "元",
        "definition": "按成本确认日期汇总与收入同期匹配的直接成本。",
        "facts": ["cost"],
    },
    "gross_profit": {
        "name": "毛利",
        "unit": "元",
        "definition": "同期确认收入减直接成本，采用管理口径，不含期间费用。",
        "facts": ["revenue", "cost"],
    },
    "gross_margin": {
        "name": "毛利率",
        "unit": "%",
        "definition": "(确认收入－直接成本)÷确认收入×100；收入为零时为空。",
        "facts": ["revenue", "cost"],
    },
    "attainment": {
        "name": "收入目标达成率",
        "unit": "%",
        "definition": "完整月份的确认收入÷同期收入目标×100；仅支持区域、经营单元、城市、产品线、月份。",
        "facts": ["revenue", "target"],
    },
    "floor": {"name": "保底收入", "unit": "元", "definition": "按月度经营预测汇总保底收入金额。", "facts": ["floor"]},
    "forecast": {"name": "滚动预测收入", "unit": "元", "definition": "按月度经营预测汇总最新滚动预测收入。", "facts": ["forecast"]},
    "outstanding_receivables": {"name": "未回款金额", "unit": "元", "definition": "应收计划金额减已核销金额。", "facts": ["outstanding_receivables"]},
    "overdue_receivables": {"name": "逾期应收", "unit": "元", "definition": "到期且尚未结清的应收余额。", "facts": ["overdue_receivables"]},
}
# 模型只能选择这些逻辑维度；物理字段映射由 query.py 统一控制。
DIMENSIONS = {
    "region": "区域",
    "city": "城市",
    "org_unit": "经营单元",
    "industry": "行业",
    "customer": "客户",
    "product_line": "产品线",
    "salesperson": "销售人员",
    "contract": "合同",
    "receivable_plan": "应收计划",
    "month": "月份",
}
Metric = Literal[
    "revenue",
    "signed",
    "payments",
    "cost",
    "gross_profit",
    "gross_margin",
    "attainment",
    "floor", "forecast", "outstanding_receivables", "overdue_receivables",
]
MasterEntity = Literal[
    "customer", "salesperson", "product", "product_line", "org_unit", "industry"
]
Dimension = Literal[
    "region",
    "city",
    "org_unit",
    "industry",
    "customer",
    "product_line",
    "salesperson",
    "contract",
    "receivable_plan",
    "month",
]


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: Dimension
    values: list[str] = Field(min_length=1, max_length=30)


class Plan(BaseModel):
    """自然语言与 SQL 之间经过严格校验的中间查询计划。"""
    model_config = ConfigDict(extra="forbid")
    query_kind: Literal["metric"] = "metric"
    metric: Metric
    dimensions: list[Dimension] = Field(default_factory=list, max_length=2)
    filters: list[Filter] = Field(default_factory=list, max_length=8)
    start_date: date
    end_date: date
    comparison: Literal["none", "yoy", "previous_period"] = "none"
    limit: int = Field(default=20, ge=1, le=100)
    sort: Literal["desc", "asc"] = "desc"
    chart: Literal["bar", "line", "pie", "table"] = "bar"

    @model_validator(mode="after")
    def consistent(self):
        # 在生成 SQL 前拦截指标和维度粒度不兼容的组合。
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 1096:
            raise ValueError("单次查询范围最多三年")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("分组维度不能重复")
        dims = set(self.dimensions) | {f.dimension for f in self.filters}
        if self.metric == "payments" and "product_line" in dims:
            raise ValueError("回款记录属于合同，暂不支持产品线拆分")
        if self.metric == "attainment":
            if dims - {"region", "city", "org_unit", "product_line", "month"}:
                raise ValueError(
                    "目标未分配到客户、行业或销售人员，不能按这些维度计算达成率"
                )
            import calendar

            if (
                self.start_date.day != 1
                or self.end_date.day
                != calendar.monthrange(self.end_date.year, self.end_date.month)[1]
            ):
                raise ValueError("目标达成率仅支持完整月份，请选择完整月或季度")
        if "contract" in dims and self.metric in {"attainment", "floor", "forecast"}:
            raise ValueError("合同维度仅适用于合同、收入、成本、回款和应收指标")
        if "receivable_plan" in dims and self.metric not in {"outstanding_receivables", "overdue_receivables"}:
            raise ValueError("应收计划维度仅适用于未回款和逾期应收指标")
        if self.metric in {"floor", "forecast"} and dims - {"region", "city", "org_unit", "product_line", "month"}:
            raise ValueError("保底和预测仅支持组织、产品线和月份维度")
        if self.metric in {"outstanding_receivables", "overdue_receivables"} and "product_line" in dims:
            raise ValueError("应收指标不支持产品线维度")
        return self


class MasterDataPlan(BaseModel):
    """客户、人员、产品等基础资料的数量和清单查询计划。"""
    model_config = ConfigDict(extra="forbid")
    query_kind: Literal["master_data"]
    entity: MasterEntity
    intent: Literal["count", "list", "count_and_list"] = "count_and_list"
    filters: list[Filter] = Field(default_factory=list, max_length=4)
    limit: int = Field(default=20, ge=1, le=100)
    sort: Literal["asc", "desc"] = "asc"
    chart: Literal["table"] = "table"

    @model_validator(mode="after")
    def supported_filters(self):
        allowed = {
            "customer": {"industry"},
            "salesperson": {"region", "city", "org_unit"},
            "product": {"product_line"},
            "product_line": set(),
            "org_unit": {"region", "city"},
            "industry": set(),
        }[self.entity]
        invalid = {item.dimension for item in self.filters} - allowed
        if invalid:
            raise ValueError("该基础资料不支持这些筛选维度：" + "、".join(sorted(invalid)))
        return self


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["query", "clarify", "unsupported"]
    plan: Plan | MasterDataPlan | None = None
    explanation: str = Field(max_length=800)

    @model_validator(mode="after")
    def need_plan(self):
        if self.action == "query" and self.plan is None:
            raise ValueError("查询需要完整计划")
        return self
