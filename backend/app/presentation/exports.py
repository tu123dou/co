"""CSV 展示与公式注入防护；不读取数据库。"""

import csv
import io

from ..contracts import QueryResult


def render_csv(result: QueryResult) -> tuple[str, str]:
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    if result.get("plan", {}).get("query_kind") == "master_data":
        columns = result["record_columns"]
        writer.writerow([column["title"] for column in columns])
        for record in result["records"]:
            values = []
            for column in columns:
                value = str(record.get(column["key"]) or "")
                values.append(
                    "'" + value
                    if value.startswith(("=", "+", "-", "@", "\t", "\r"))
                    else value
                )
            writer.writerow(values)
        return out.getvalue(), "master-data-result.csv"
    writer.writerow(
        [
            "分组",
            result["metric"]["name"] + "（" + result["metric"]["unit"] + "）",
            "对比值",
            "变化率（%）",
            "差额/百分点",
        ]
    )
    for r in result["rows"]:
        label = r["label"]
        label = (
            "'" + label if label.startswith(("=", "+", "-", "@", "\t", "\r")) else label
        )
        writer.writerow(
            [label, r["value"], r["previous"], r["change"], r["difference"]]
        )
    return out.getvalue(), "query-result.csv"
