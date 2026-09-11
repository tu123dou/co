"""Versioned business catalog and constrained query contract; no model-authored SQL."""

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

METRICS = {
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
}
DIMENSIONS = {
    "region": "区域",
    "city": "城市",
    "org_unit": "经营单元",
    "industry": "行业",
    "customer": "客户",
    "product_line": "产品线",
    "salesperson": "销售人员",
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
]
Dimension = Literal[
    "region",
    "city",
    "org_unit",
    "industry",
    "customer",
    "product_line",
    "salesperson",
    "month",
]


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: Dimension
    values: list[str] = Field(min_length=1, max_length=30)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
        return self


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["query", "clarify", "unsupported"]
    plan: Plan | None = None
    explanation: str = Field(max_length=800)

    @model_validator(mode="after")
    def need_plan(self):
        if self.action == "query" and self.plan is None:
            raise ValueError("查询需要完整计划")
        return self
