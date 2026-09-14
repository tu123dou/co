"""从可信业务目录生成说明；任何输入都不能展开应用表或内部配置。"""

from ..catalog import TABLE_CATALOG
from ..contracts import DatasetInfo
from ..information import InformationRequest
from ..query.compiler import ALLOWED_TABLES
from ..semantic import DIMENSIONS, METRICS


def business_tables() -> dict[str, dict]:
    return {
        name: spec
        for name, spec in TABLE_CATALOG.items()
        if name.startswith("analytics.") and name.split(".", 1)[1] in ALLOWED_TABLES
    }


def table_title(spec: dict) -> str:
    return spec["comment"].split("。", 1)[0]


def selected_tables(table: str | None) -> dict[str, dict]:
    tables = business_tables()
    if table is None:
        return tables
    # 只允许白名单中的完整表名、短名或目录中文名称，不回显未知名称。
    return {
        name: spec
        for name, spec in tables.items()
        if table in {name, name.split(".", 1)[1], table_title(spec)}
    }


def information_answer(request: InformationRequest, dataset: DatasetInfo | None) -> str:
    sections = []
    tables = business_tables()
    for topic in dict.fromkeys(request.topics):
        if topic == "identity":
            sections.append(
                "我是经管之星，你的 AI 经营问数助手。你可以用自然语言了解业务数据、查询经营指标，并查看结果的口径与取数依据。也可以先问我“有哪些数据表”或“我可以问什么”。"
            )
        elif topic == "table_count":
            sections.append(
                f"当前可查询的业务数据表共有 {len(tables)} 张，涵盖组织、客户、产品、销售合同、收入、成本、回款、应收和目标预测。此处只统计业务数据表。"
            )
        elif topic in {"tables", "fields"}:
            selected = selected_tables(request.table)
            if not selected:
                sections.append(
                    "当前仅提供可查询业务数据表的说明。请从“有哪些业务表”的结果中选择表名，再询问其用途或字段。"
                )
                continue
            if topic == "fields" and request.table is None:
                sections.append(
                    "请指定一张业务数据表，例如“销售合同主表有哪些字段”。你也可以先问“有哪些业务表”。"
                )
                continue
            entries = []
            for index, (name, spec) in enumerate(selected.items(), 1):
                entry = f"{index}. {table_title(spec)}（{name.split('.', 1)[1]}）\n{spec['comment'].split('。', 1)[1]}"
                if topic == "fields":
                    entry += "\n字段说明：\n" + "\n".join(
                        f"• {key}：{description}"
                        for key, description in spec["columns"].items()
                    )
                entries.append(entry)
            sections.append(
                f"以下为 {len(selected)} 张业务数据表的说明：\n\n"
                + "\n\n".join(entries)
            )
        elif topic == "date_range":
            if dataset is None:
                raise ValueError("数据范围说明需要数据版本")
            start, cutoff = dataset["start_date"], dataset["cutoff_date"]
            sections.append(
                f"当前数据集的可查询日期范围为 {start} 至 {cutoff}，数据截止 {cutoff}。\n“今年”“上个月”等相对时间以数据截止日为参考，不按今天推算。单张表实际有记录的日期可能少于这个范围；基础资料查询使用当前快照，不按日期筛选。"
            )
        elif topic == "capabilities":
            sections.append(
                "你可以这样使用我：\n"
                "• 了解数据：询问业务表数量、用途、字段和数据日期范围。\n"
                "• 查询经营指标："
                + "、".join(spec["name"] for spec in METRICS.values())
                + "。\n"
                "• 做汇总、排名、月度趋势、维度拆分及同比/环比分析。\n"
                "• 查询客户、销售人员、产品等基础资料数量与清单，以及受控的合同清单和应收计划。\n"
                "• 连续追问、查看指标口径与取数依据，导出支持的查询结果。\n"
                "提问时建议说明指标、时间和分析维度，例如“今年各经营单元确认收入排名”。\n"
                "当前不支持任意 SQL、任意逐笔财务流水、跨数据源查询或没有数据依据的因果判断。"
            )
        elif topic == "metrics":
            metrics = {
                key: spec
                for key, spec in METRICS.items()
                if request.metric is None or request.metric in {key, spec["name"]}
            }
            sections.append(
                "指标口径：\n"
                + "\n".join(
                    f"• {spec['name']}（{spec['unit']}）：{spec['definition']}"
                    for spec in metrics.values()
                )
                if metrics
                else "当前没有该指标的已定义口径。可以先问“支持哪些指标”。"
            )
        elif topic == "dimensions":
            sections.append(
                "支持的分析维度包括："
                + "、".join(DIMENSIONS.values())
                + "。\n不同指标允许的维度不同：回款和应收不支持产品线拆分；目标达成率仅支持完整月份及已分配目标的组织、产品线和月份维度。"
            )
        elif topic == "data_source":
            sections.append(
                "当前业务数据是用于演示的虚构经营台账，覆盖合同、产品、收入、成本、回款、应收及目标预测，不代表真实企业经营情况。\n系统按当前已加载的数据版本提供分析，不保证实时同步，也没有承诺固定更新频率。数据是否更新以及覆盖到哪天，请以当前数据日期范围为准。"
            )
    return "\n\n".join(sections)
