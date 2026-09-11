"""Read-only integration checks against the seeded, project-local database."""

import os
import pytest
from datetime import date
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.db import engine, query_engine
from app.query import execute_plan
from app.semantic import Plan

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


def test_exact_twenty_tables():
    assert (
        scalar(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('app','analytics') AND table_type='BASE TABLE'"
        )
        == 20
    )


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


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM app.users",
        "UPDATE analytics.contracts SET status=status WHERE false",
        "CREATE TABLE analytics.illegal(id integer)",
    ],
)
def test_analyst_denied(sql):
    with query_engine.begin() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(text(sql))


def test_empty_and_zero_baseline():
    r = run(start_date="2024-01-01", end_date="2024-01-31")
    assert r["empty"] and r["total"] == 0


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
