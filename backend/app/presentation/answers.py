"""由同一查询结果生成确定性摘要与展示步骤，不访问数据库或模型。"""

from ..contracts import AnalysisStep, DatasetInfo, QueryPlan, QueryResult, QueryRun
from ..semantic import DIMENSIONS, MASTER_ENTITY_NAMES, METRICS, MasterDataPlan

SOURCE_LABELS = {
    "revenue": [
        "收入确认流水（analytics.revenue_entries）",
        "合同明细（analytics.contract_items）",
    ],
    "signed": [
        "合同台账（analytics.contracts）",
        "合同明细（analytics.contract_items）",
    ],
    "payments": [
        "回款流水（analytics.payment_entries）",
        "合同台账（analytics.contracts）",
    ],
    "cost": [
        "成本确认流水（analytics.cost_entries）",
        "合同明细（analytics.contract_items）",
    ],
    "target": ["月度经营目标（analytics.monthly_targets）"],
    "floor": ["月度经营目标（analytics.monthly_targets）"],
    "forecast": ["月度经营目标（analytics.monthly_targets）"],
    "outstanding_receivables": [
        "合同应收计划（analytics.receivable_entries）",
        "合同台账（analytics.contracts）",
    ],
    "overdue_receivables": [
        "合同应收计划（analytics.receivable_entries）",
        "合同台账（analytics.contracts）",
    ],
}
DIMENSION_LABELS = DIMENSIONS
CHART_LABELS = {"bar": "柱状图", "line": "折线图", "pie": "占比图", "table": "数据表"}


def summary(result: QueryResult, plan: QueryPlan) -> str:
    if isinstance(plan, MasterDataPlan):
        name = MASTER_ENTITY_NAMES[plan.entity]
        if result["empty"]:
            return f"没有找到符合条件的{name}资料。"
        if plan.intent == "count":
            return f"符合条件的{name}共有 {result['total_count']:,} 个。"
        return f"符合条件的{name}共有 {result['total_count']:,} 个，当前列出 {len(result['records'])} 个。"
    metric = METRICS[plan.metric]
    unit = metric["unit"]

    def fmt(v):
        return "暂无可计算数据" if v is None else f"{v:,.2f}{unit}"

    if result["empty"]:
        return "所选范围没有业务记录。请检查筛选条件或更换时间范围。"
    sentence = f"{plan.start_date} 至 {plan.end_date}，{metric['name']}为 {fmt(result['total'])}。"
    if result["previous_total"] is not None:
        sentence += f"对比期间为 {fmt(result['previous_total'])}。"
        if unit == "%" and result["difference"] is not None:
            sentence += f"变化 {result['difference']:+.2f} 个百分点。"
        elif result["change"] is not None:
            sentence += f"{'同比' if plan.comparison == 'yoy' else '环比'} {result['change']:+.2f}%。"
        else:
            sentence += "对比基数为零，增幅不适用。"
    if plan.dimensions and result["rows"]:
        valid = [r for r in result["rows"] if r["value"] is not None]
        if valid:
            top = max(valid, key=lambda r: r["value"])
            sentence += f"当前展示中，{top['label']}最高，为 {fmt(top['value'])}。"
    if result["truncated"]:
        sentence += (
            f"共 {result['group_count']} 组，展示前 {plan.limit} 组；汇总包含全部分组。"
        )
    return sentence


def analysis_intro(
    question: str, explanation: str, plan: QueryPlan, dataset: DatasetInfo
) -> list[AnalysisStep]:
    """生成查询执行前已经确定的数据源和结构化解析步骤。"""
    if isinstance(plan, MasterDataPlan):
        name, table = {
            "customer": ("客户", "analytics.customers"),
            "salesperson": ("销售人员", "analytics.salespeople"),
            "product": ("产品", "analytics.products"),
            "product_line": ("产品线", "analytics.product_lines"),
            "org_unit": ("经营单元", "analytics.org_units"),
            "industry": ("行业", "analytics.industries"),
        }[plan.entity]
        filters = [
            f"{DIMENSION_LABELS[f.dimension]}={'、'.join(f.values)}"
            for f in plan.filters
        ]
        return [
            {
                "key": "source",
                "title": "选择数据表与数据时效",
                "status": "complete",
                "items": [
                    f"选用数据源：{name}基础资料（{table}）",
                    "数据时效：当前基础资料快照",
                    f"业务口径：每行代表一个{name}对象",
                ],
            },
            {
                "key": "plan",
                "title": "解析与计算逻辑",
                "status": "complete",
                "items": [
                    f"问题：{question}",
                    f"解析结果：{explanation}",
                    f"查询对象：{name}；查询方式：{plan.intent}",
                    "筛选条件：" + ("；".join(filters) if filters else "全部"),
                    f"最多展示 {plan.limit} 条",
                ],
            },
        ]
    sources = []
    for fact in METRICS[plan.metric]["facts"]:
        for source in SOURCE_LABELS[fact]:
            if source not in sources:
                sources.append(source)
    filters = [
        f"{DIMENSION_LABELS[f.dimension]}={'、'.join(f.values)}" for f in plan.filters
    ]
    dimensions = (
        "、".join(DIMENSION_LABELS[d] for d in plan.dimensions) or "不分组（汇总值）"
    )
    return [
        {
            "key": "source",
            "title": "选择数据表与数据时效",
            "status": "complete",
            "items": [
                "选用数据源：" + "、".join(sources),
                f"数据覆盖：{dataset['start_date']} 至 {dataset['cutoff_date']}",
                "业务口径：" + METRICS[plan.metric]["definition"],
            ],
        },
        {
            "key": "plan",
            "title": "解析与计算逻辑",
            "status": "complete",
            "items": [
                f"问题：{question}",
                f"解析结果：{explanation}",
                f"指标：{METRICS[plan.metric]['name']}；分析维度：{dimensions}",
                "筛选条件：" + ("；".join(filters) if filters else "全部"),
                f"排序：{'从高到低' if plan.sort == 'desc' else '从低到高'}；最多展示 {plan.limit} 组",
            ],
        },
    ]


def analysis_sql_step(executions):
    """生成 SQL 展示步骤，同时提供可执行版本和中文口径版本。"""
    return {
        "key": "sql",
        "title": "执行取数 SQL",
        "status": "complete",
        "items": [],
        "executions": [
            {
                "name": "本期 SQL" if index == 0 else "对比期 SQL",
                "executable_sql": execution["executable_sql"],
                "business_sql": execution["business_sql"],
            }
            for index, execution in enumerate(executions)
        ],
    }


def analysis_process(
    question: str,
    explanation: str,
    plan: QueryPlan,
    result: QueryResult,
    dataset: DatasetInfo,
) -> list[AnalysisStep]:
    """根据真实计划和执行结果生成前端可展示、可审计的五步过程。"""
    if isinstance(plan, MasterDataPlan):
        preview = [
            "、".join(str(value) for value in row.values() if value is not None)
            for row in result["records"][:5]
        ]
    else:
        preview = [
            f"{row['label']}：{row['value']:,.2f}{METRICS[plan.metric]['unit']}"
            for row in result["rows"][:5]
            if row["value"] is not None
        ]
    return [
        *analysis_intro(question, explanation, plan, dataset),
        analysis_sql_step(result["executions"]),
        {
            "key": "result",
            "title": "展示取数结果",
            "status": "complete",
            "items": [
                (
                    f"资料总数：{result['total_count']:,} 条"
                    if isinstance(plan, MasterDataPlan)
                    else (
                        f"汇总结果：{result['total']:,.2f}{METRICS[plan.metric]['unit']}"
                        if result["total"] is not None
                        else "汇总结果：暂无可计算数据"
                    )
                ),
                "前五项：" + ("；".join(preview) if preview else "无明细记录"),
                "预览方式：" + CHART_LABELS[plan.chart],
            ],
        },
        {
            "key": "done",
            "title": "执行结束",
            "status": "complete",
            "items": ["全流程取数和分析已经完成，最终结果已在当前回答中生成。"],
        },
    ]


def answer_metadata(
    run: QueryRun,
    dataset: DatasetInfo,
    complete_process: list[AnalysisStep],
    completed_at: str,
    duration_ms: int,
) -> QueryResult:
    return {
        "status": run.status,
        "plan": run.plan.model_dump(mode="json"),
        "metric": {
            "name": MASTER_ENTITY_NAMES[run.plan.entity],
            "unit": "个",
            "definition": "基础资料对象数量",
        }
        if isinstance(run.plan, MasterDataPlan)
        else METRICS[run.plan.metric],
        "dataset_version": dataset["version"],
        "cutoff_date": str(dataset["cutoff_date"]),
        "model": run.context.model,
        "duration_ms": duration_ms,
        "completed_at": completed_at,
        "usage": run.usage,
        "analysis_process": complete_process,
        "suggestions": (
            ["查看前50个", "按名称排序", "查看其他基础资料"]
            if isinstance(run.plan, MasterDataPlan)
            else [
                "只看上海" if run.plan.filters else "只看华东区",
                "换成按区域展示" if "month" in run.plan.dimensions else "换成按月展示",
                "查看同一范围的毛利率"
                if run.plan.comparison != "none"
                else "与去年同期相比",
            ]
        )
        if run.context.suggestions_enabled
        else [],
    }
