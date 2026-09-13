"""数据库集成测试：验证迁移、只读权限、表结构和业务数据口径。"""

import os
from datetime import date

import pytest
from app.db import engine, query_engine
from app.query import execute_plan
from app.semantic import MasterDataPlan, Plan
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE") != "1",
    reason="Set TEST_DATABASE=1 for project database checks",
)


def run(**kw):
    return execute_plan(
        Plan(
            **{
                "metric": "revenue",
                "start_date": "2026-01-01",
                "end_date": "2026-08-31",
                **kw,
            }
        ),
        query_engine,
        date(2026, 8, 31),
        date(2024, 1, 1),
    )


def scalar(sql):
    with engine.connect() as conn:
        return conn.scalar(text(sql))


def test_exact_twenty_seven_tables():
    assert (
        scalar(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('app','analytics') AND table_type='BASE TABLE'"
        )
        == 27
    )


def test_database_comments_are_complete_and_include_grain():
    with engine.connect() as conn:
        tables = (
            conn.execute(
                text(
                    """
                SELECT n.nspname AS schema_name, c.relname AS table_name,
                       obj_description(c.oid, 'pg_class') AS comment
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname IN ('app', 'analytics') AND c.relkind = 'r'
                """
                )
            )
            .mappings()
            .all()
        )
        assert len(tables) == 27
        assert all(
            row["comment"] and "用途：" in row["comment"] and "粒度：" in row["comment"]
            for row in tables
        )
        undocumented = conn.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname IN ('app', 'analytics')
                  AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
                  AND col_description(c.oid, a.attnum) IS NULL
                """
            )
        )
        assert undocumented == 0
        alembic = (
            conn.execute(
                text(
                    """
                SELECT obj_description('public.alembic_version'::regclass, 'pg_class') AS table_comment,
                       col_description('public.alembic_version'::regclass, 1) AS column_comment
                """
                )
            )
            .mappings()
            .one()
        )
        assert alembic["table_comment"] and alembic["column_comment"]


@pytest.mark.parametrize(
    "metric,sql",
    [
        (
            "revenue",
            "SELECT SUM(amount_ex_tax) FROM analytics.revenue_entries WHERE recognition_date BETWEEN '2026-01-01' AND '2026-08-31'",
        ),
        (
            "cost",
            "SELECT SUM(amount_ex_tax) FROM analytics.cost_entries WHERE cost_date BETWEEN '2026-01-01' AND '2026-08-31'",
        ),
        (
            "payments",
            "SELECT SUM(amount_ex_tax) FROM analytics.payment_entries WHERE payment_date BETWEEN '2026-01-01' AND '2026-08-31'",
        ),
        (
            "signed",
            "SELECT SUM(ci.amount_ex_tax) FROM analytics.contract_items ci JOIN analytics.contracts c ON c.id=ci.contract_id WHERE c.signed_date BETWEEN '2026-01-01' AND '2026-08-31' AND c.status!='cancelled'",
        ),
    ],
)
def test_independent_totals(metric, sql):
    assert run(metric=metric)["total"] == pytest.approx(float(scalar(sql)))


def test_grouping_preserves_totals():
    r = run(dimensions=["product_line"])
    assert sum(x["value"] for x in r["rows"]) == pytest.approx(r["total"])


def test_margin_is_weighted():
    r = run(metric="gross_margin", dimensions=["product_line"])
    expected = (run()["total"] - run(metric="cost")["total"]) / run()["total"] * 100
    assert r["total"] == pytest.approx(expected)


def test_target_not_duplicated():
    r = run(metric="attainment", dimensions=["product_line"])
    target = scalar(
        "SELECT SUM(revenue_target) FROM analytics.monthly_targets WHERE month BETWEEN '2026-01-01' AND '2026-08-31'"
    )
    assert r["total"] == pytest.approx(run()["total"] / float(target) * 100)


def test_month_yoy_aligns():
    r = run(dimensions=["month"], comparison="yoy")
    assert len(r["rows"]) == 8
    assert all(x["previous"] > 0 for x in r["rows"])
    assert all(x["label"].startswith("2026-") for x in r["rows"])


def test_no_revenue_beyond_contract_amount():
    assert (
        scalar(
            "SELECT count(*) FROM (SELECT ci.id FROM analytics.contract_items ci JOIN analytics.revenue_entries r ON r.contract_item_id=ci.id GROUP BY ci.id,ci.amount_ex_tax HAVING SUM(r.amount_ex_tax)>ci.amount_ex_tax) x"
        )
        == 0
    )


def test_no_overpayment():
    assert (
        scalar(
            "WITH amounts AS (SELECT contract_id,SUM(amount_ex_tax) amount FROM analytics.contract_items GROUP BY contract_id), payments AS (SELECT contract_id,SUM(amount_ex_tax) amount FROM analytics.payment_entries GROUP BY contract_id) SELECT count(*) FROM amounts a JOIN payments p USING(contract_id) WHERE p.amount>a.amount"
        )
        == 0
    )


def test_receivables_reconcile_to_payments_and_include_overdue():
    assert scalar("SELECT SUM(settled_amount_ex_tax) FROM analytics.receivable_entries") == scalar("SELECT SUM(amount_ex_tax) FROM analytics.payment_entries")
    assert scalar("SELECT count(*) FROM analytics.receivable_entries WHERE status='逾期' AND settled_amount_ex_tax<amount_ex_tax") > 0


@pytest.mark.parametrize("metric", ["floor", "forecast", "outstanding_receivables", "overdue_receivables"])
def test_computing_business_metrics_return_data(metric):
    result = run(metric=metric)
    assert result["total"] > 0


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM app.users",
        "UPDATE analytics.contracts SET status=status WHERE false",
        "CREATE TABLE analytics.illegal(id integer)",
    ],
)
def test_analyst_denied(sql):
    with query_engine.begin() as conn, pytest.raises(DBAPIError):
        conn.execute(text(sql))


def test_empty_and_zero_baseline():
    r = run(start_date="2024-01-01", end_date="2024-01-31")
    assert r["empty"] and r["total"] == 0


def test_master_data_returns_exact_total_and_limited_salespeople():
    result = execute_plan(
        MasterDataPlan(query_kind="master_data", entity="salesperson", intent="count_and_list", limit=20),
        query_engine,
        date(2026, 8, 31),
        date(2024, 1, 1),
    )
    assert result["total_count"] == scalar("SELECT count(*) FROM analytics.salespeople")
    assert len(result["records"]) == 20
    assert result["record_columns"][1]["title"] == "销售人员"


def test_month_filter_applies_to_previous_year():
    from app.semantic import Filter

    r = run(
        dimensions=["month"],
        filters=[Filter(dimension="month", values=["2026-08"])],
        comparison="yoy",
    )
    assert len(r["rows"]) == 1 and r["rows"][0]["previous"] > 0
    direct = run(start_date="2025-08-01", end_date="2025-08-31")
    assert r["previous_total"] == pytest.approx(direct["total"])
