"""失败用例复测脚本：只重新运行上次模型评测中未通过的案例。"""

import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import CASES
from app.llm import interpret
from app.repositories.catalog import get_catalog, dataset_info, validate_filters
from app.query import execute_plan
from app.db import query_engine


async def main():
    p = Path("docs/model-evaluation.json")
    report = json.loads(p.read_text())
    report.setdefault("first_run_passed", report["passed"])
    cat = get_catalog()
    d = dataset_info()
    for row in report["cases"]:
        if row["passed"]:
            continue
        q = row["question"]
        expected = next(c for c in CASES if c[0] == q)
        a, u = await interpret(
            q,
            {},
            [],
            cat,
            {k: str(d[k]) for k in ["version", "start_date", "cutoff_date"]},
        )
        plan = a.plan
        validate_filters(plan, cat)
        execute_plan(plan, query_engine, d["cutoff_date"], d["start_date"])
        passed = (
            a.action == "query"
            and plan.metric == expected[1]
            and (expected[2] is None or expected[2] in plan.dimensions)
            and plan.comparison == expected[3]
        )
        row["initial_error"] = row.pop("error", None)
        row.update(
            passed=passed, retested=True, response=a.model_dump(mode="json"), usage=u
        )
        print(q, passed, flush=True)
    report["passed"] = sum(r["passed"] for r in report["cases"])
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("FINAL", report["passed"], report["total"])


asyncio.run(main())
