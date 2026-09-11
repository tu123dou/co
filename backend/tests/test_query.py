from datetime import date
import pytest
from pydantic import ValidationError
from app.semantic import Plan, Filter, METRICS, DIMENSIONS
from app.query import compile_plan, previous_dates, validate_sql, value_of


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
    sql, params = compile_plan(
        plan(
            metric=metric,
            dimensions=["product_line"] if metric != "payments" else ["region"],
        )
    )
    assert "analytics." in sql and params["start_date"] == date(2026, 1, 1)


@pytest.mark.parametrize("dim", list(DIMENSIONS))
def test_compiles_all_dimensions(dim):
    compile_plan(plan(dimensions=[dim]))


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
