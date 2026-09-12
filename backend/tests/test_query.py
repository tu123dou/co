"""查询引擎测试：验证计划校验、SQL 编译、指标计算和安全边界。"""

from datetime import date

import pytest
from app.query import (
    compile_plan,
    previous_dates,
    render_business_sql,
    render_executable_sql,
    validate_sql,
    value_of,
)
from app.schema import metadata
from app.semantic import DIMENSIONS, METRICS, Filter, Plan
from pydantic import ValidationError


def plan(**kwargs):
    return Plan(
        **{
            "metric": "revenue",
            "start_date": "2026-01-01",
            "end_date": "2026-08-31",
            **kwargs,
        }
    )


@pytest.mark.parametrize("metric", list(METRICS))
def test_compiles_all_metrics(metric):
    dimension = "region" if metric in {"payments", "outstanding_receivables", "overdue_receivables"} else "product_line"
    sql, params = compile_plan(
        plan(
            metric=metric,
            dimensions=[dimension],
        )
    )
    assert "analytics." in sql and params["start_date"] == date(2026, 1, 1)


@pytest.mark.parametrize("dim", list(DIMENSIONS))
def test_compiles_all_dimensions(dim):
    metric = "overdue_receivables" if dim == "receivable_plan" else "revenue"
    compile_plan(plan(metric=metric, dimensions=[dim]))


@pytest.mark.parametrize("dim", list(DIMENSIONS))
def test_compiles_all_filter_dimensions(dim):
    metric = "overdue_receivables" if dim == "receivable_plan" else "revenue"
    compile_plan(plan(metric=metric, filters=[Filter(dimension=dim, values=["测试值"])]))


def test_payment_total_only_joins_contract_for_status():
    sql, _ = compile_plan(plan(metric="payments"))
    assert "analytics.payment_entries" in sql
    assert "analytics.contracts" in sql
    assert "analytics.org_units" not in sql
    assert "analytics.customers" not in sql
    assert "analytics.industries" not in sql
    assert "analytics.salespeople" not in sql


def test_payment_dimension_adds_only_required_join():
    sql, _ = compile_plan(plan(metric="payments", dimensions=["industry"]))
    assert "analytics.customers" in sql
    assert "analytics.industries" in sql
    assert "analytics.org_units" not in sql
    assert "analytics.salespeople" not in sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE analytics.contracts",
        "SELECT * FROM app.users",
        "SELECT 1; SELECT 2",
        "SELECT pg_read_file('/etc/passwd')",
        "WITH x AS (DELETE FROM analytics.contracts RETURNING *) SELECT * FROM x",
        "SELECT * INTO foo FROM analytics.contracts",
        "SELECT * FROM analytics.contracts FOR UPDATE",
        "SELECT * FROM other.analytics.contracts",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_filters_are_parameters():
    value = "华东' OR true --"
    sql, params = compile_plan(
        plan(filters=[Filter(dimension="region", values=[value])])
    )
    assert value not in sql and params["f0_0"] == value


def test_display_sql_is_copyable_and_business_readable():
    current = plan(
        metric="signed",
        dimensions=["product_line"],
        filters=[Filter(dimension="product_line", values=["通用计算"])],
    )
    sql, params = compile_plan(current)
    executable = render_executable_sql(sql, params)
    assert ":start_date" not in executable
    assert "CAST('2026-01-01' AS DATE)" in executable
    assert "'通用计算'" in executable
    validate_sql(executable)
    readable = render_business_sql(current)
    assert "SELECT 产品线" in readable
    assert "合同明细 JOIN 合同台账" in readable
    assert "AS 签约额" in readable


def test_customer_contract_list_uses_controlled_grouping():
    sql, params = compile_plan(
        plan(
            metric="signed",
            dimensions=["contract"],
            filters=[Filter(dimension="customer", values=["明瀚教育科研集团0034"])],
            chart="table",
        )
    )
    assert "ct.number" in sql and "ct.name" in sql
    assert params["f0_0"] == "明瀚教育科研集团0034"


def test_highest_customer_receivable_plan_uses_controlled_grouping():
    sql, params = compile_plan(
        plan(
            metric="overdue_receivables",
            dimensions=["receivable_plan"],
            filters=[Filter(dimension="customer", values=["明瀚教育科研集团0034"])],
            sort="desc",
            limit=1,
            chart="table",
        )
    )
    assert "f.due_date" in sql and "CAST(f.id AS TEXT)" in sql
    assert params["f0_0"] == "明瀚教育科研集团0034"


def test_receivable_plan_dimension_rejects_unrelated_metric():
    with pytest.raises(ValidationError):
        plan(metric="revenue", dimensions=["receivable_plan"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metric": "payments", "dimensions": ["product_line"]},
        {"metric": "attainment", "dimensions": ["industry"]},
        {"metric": "attainment", "start_date": "2026-01-02"},
        {"end_date": "2025-01-01"},
        {"dimensions": ["month", "month"]},
    ],
)
def test_invalid_business_plan(kwargs):
    with pytest.raises(ValidationError):
        plan(**kwargs)


def test_calendar_quarter_comparison():
    assert previous_dates(
        plan(
            start_date="2026-04-01", end_date="2026-06-30", comparison="previous_period"
        )
    ) == (date(2026, 1, 1), date(2026, 3, 31))


def test_leap_year_comparison():
    assert previous_dates(
        plan(start_date="2024-02-01", end_date="2024-02-29", comparison="yoy")
    ) == (date(2023, 2, 1), date(2023, 2, 28))


def test_ratio_and_zero():
    assert value_of({"revenue": 100, "cost": 40}, "gross_margin") == 60
    assert value_of({"revenue": 0}, "gross_margin") is None
    assert value_of({"revenue": 90, "target": 100}, "attainment") == 90


def test_every_domain_table_and_column_has_chinese_catalog_comment():
    assert len(metadata.tables) == 27
    for table in metadata.tables.values():
        assert table.comment
        assert "用途：" in table.comment
        assert "粒度：" in table.comment
        assert any("\u4e00" <= char <= "\u9fff" for char in table.comment)
        for column in table.c:
            assert column.comment, f"{table.fullname}.{column.name} 缺少中文列注释"
            assert any("\u4e00" <= char <= "\u9fff" for char in column.comment)
