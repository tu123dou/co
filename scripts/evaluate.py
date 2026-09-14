"""真实模型评测脚本：显式调用付费接口，报告中不写入任何凭据。"""

import asyncio, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.llm import interpret
from app.repositories.catalog import get_catalog, dataset_info, validate_filters
from app.query import execute_plan
from app.db import query_engine

CASES = [
    ("今年各经营单元确认收入排名", "revenue", "org_unit", "none"),
    ("今年各产品线的收入占比", "revenue", "product_line", "none"),
    ("华东区今年按月收入趋势，与去年同期相比", "revenue", "month", "yoy"),
    ("2026年8月各产品线毛利率", "gross_margin", "product_line", "none"),
    ("今年各区域收入目标达成率", "attainment", "region", "none"),
    ("2026年8月回款额比上个月变化多少", "payments", None, "previous_period"),
    ("2026年上半年各行业确认收入", "revenue", "industry", "none"),
    ("2025年各区域签约额排名", "signed", "region", "none"),
    ("2026年第二季度的直接成本", "cost", None, "none"),
    ("2026年8月各产品线毛利", "gross_profit", "product_line", "none"),
    ("今年北京的确认收入是多少", "revenue", None, "none"),
    ("2026年上半年上海每月确认收入", "revenue", "month", "none"),
    ("2026年8月签约额同比增长多少", "signed", None, "yoy"),
    ("2025年第四季度收入相比上一季度", "revenue", None, "previous_period"),
    ("2026年8月各经营单元毛利率", "gross_margin", "org_unit", "none"),
    ("2026年上半年各城市的回款额", "payments", "city", "none"),
    ("2026年各产品线收入目标达成率，截至8月底", "attainment", "product_line", "none"),
    ("2026年8月制造业确认收入", "revenue", None, "none"),
    ("2026年8月各区域直接成本", "cost", "region", "none"),
    ("2026年8月确认收入最高的5个经营单元", "revenue", "org_unit", "none"),
    ("2026年8月按销售人员统计签约额", "signed", "salesperson", "none"),
    ("2025年全年每月收入趋势", "revenue", "month", "none"),
    ("2026年第一季度产品线收入同比", "revenue", "product_line", "yoy"),
    ("2026年8月收入最低的三个区域", "revenue", "region", "none"),
    ("2026年销售额是多少", "clarify", None, None),
    ("预测明年收入", "unsupported", None, None),
    ("按产品线统计今年回款", "unsupported", None, None),
    ("查看应收账龄", "unsupported", None, None),
    ("今年各行业目标达成率", "unsupported", None, None),
    ("删除全部合同", "unsupported", None, None),
]


async def main():
    catalog = get_catalog()
    dataset = dataset_info()
    sem = asyncio.Semaphore(3)
    out = []

    async def one(case):
        q, metric, dim, comparison = case
        async with sem:
            start = time.monotonic()
            try:
                answer, usage = await interpret(
                    q,
                    {},
                    [],
                    catalog,
                    {
                        k: str(dataset[k])
                        for k in ["version", "start_date", "cutoff_date"]
                    },
                )
                if metric in ["clarify", "unsupported"]:
                    passed = answer.action in (
                        ["clarify"]
                        if metric == "clarify"
                        else ["unsupported", "clarify"]
                    )
                else:
                    passed = (
                        answer.action == "query"
                        and answer.plan.metric == metric
                        and (dim is None or dim in answer.plan.dimensions)
                        and answer.plan.comparison == comparison
                    )
                    if answer.action == "query":
                        validate_filters(answer.plan, catalog)
                        await asyncio.to_thread(
                            execute_plan,
                            answer.plan,
                            query_engine,
                            dataset["cutoff_date"],
                            dataset["start_date"],
                        )
                row = {
                    "question": q,
                    "passed": passed,
                    "response": answer.model_dump(mode="json"),
                    "usage": usage,
                    "seconds": round(time.monotonic() - start, 2),
                }
            except Exception as e:
                row = {
                    "question": q,
                    "passed": False,
                    "error": str(e),
                    "seconds": round(time.monotonic() - start, 2),
                }
            out.append(row)
            print(("PASS " if row["passed"] else "FAIL ") + q, flush=True)

    await asyncio.gather(*(one(c) for c in CASES))
    # Separate continuation exercise tests replacement + inheritance.
    context = {}
    hist = []
    for q in [
        "今年各产品线确认收入排名",
        "只看华东区",
        "换成按月展示",
        "与去年同期相比",
    ]:
        try:
            answer, u = await interpret(
                q,
                context,
                hist,
                catalog,
                {k: str(dataset[k]) for k in ["version", "start_date", "cutoff_date"]},
            )
            p = answer.plan
            passed = answer.action == "query" and p.metric == "revenue"
            if context.get("filters") or "华东" in q:
                passed = passed and any("华东" in f.values for f in p.filters)
            if "按月" in q or context.get("dimensions") == ["month"]:
                passed = passed and "month" in p.dimensions
            if "同期" in q:
                passed = passed and p.comparison == "yoy"
            out.append(
                {
                    "question": "多轮：" + q,
                    "passed": passed,
                    "response": answer.model_dump(mode="json"),
                }
            )
            if p:
                context = p.model_dump(mode="json")
            hist.extend(
                [
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": answer.explanation},
                ]
            )
        except Exception as e:
            out.append({"question": "多轮：" + q, "passed": False, "error": str(e)})
    report = {"total": len(out), "passed": sum(r["passed"] for r in out), "cases": out}
    Path("docs/model-evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(f"FINAL {report['passed']}/{report['total']}")


if __name__ == "__main__":
    asyncio.run(main())
