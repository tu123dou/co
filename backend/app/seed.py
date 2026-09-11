"""Deterministic synthetic B2B software sales ledger, never overwrites existing data."""

import calendar, random
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from . import schema as s
from .db import engine
from .config import settings
from .auth import hash_password
from .semantic import METRICS, DIMENSIONS

SEED = 20260911
START = date(2024, 1, 1)
CUTOFF = date(2026, 8, 31)
VERSION = "synthetic-sales-v1"
ORG = [
    ("北京代表处", "华北", "北京"),
    ("上海代表处", "华东", "上海"),
    ("浙江代表处", "华东", "杭州"),
    ("江苏代表处", "华东", "南京"),
    ("山东代表处", "华北", "济南"),
    ("广东代表处", "华南", "广州"),
    ("深圳代表处", "华南", "深圳"),
    ("四川代表处", "西南", "成都"),
    ("湖北代表处", "华中", "武汉"),
    ("陕西代表处", "西北", "西安"),
]
LINES = ["企业管理软件", "数据智能平台", "云基础服务", "信息安全", "实施与运维"]
INDUSTRIES = ["制造业", "金融服务", "政企公共事业", "零售消费", "交通物流", "医疗健康"]


def shift(d, months):
    idx = d.year * 12 + d.month - 1 + months
    y, m = divmod(idx, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def cents(amount):
    return Decimal(str(amount)).quantize(Decimal(".01"))


def seed():
    rng = random.Random(SEED)
    with engine.begin() as conn:
        conn.execute(
            __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(9260911)")
        )
        if conn.scalar(select(func.count()).select_from(s.dataset_versions)):
            return {"status": "already_seeded"}
        if conn.scalar(select(func.count()).select_from(s.contracts)):
            raise RuntimeError("Existing business data found; refusing to overwrite")
        conn.execute(
            s.org_units.insert(),
            [
                {"id": i + 1, "name": n, "region": r, "city": c}
                for i, (n, r, c) in enumerate(ORG)
            ],
        )
        conn.execute(
            s.industries.insert(),
            [{"id": i + 1, "name": n} for i, n in enumerate(INDUSTRIES)],
        )
        conn.execute(
            s.product_lines.insert(),
            [{"id": i + 1, "name": n} for i, n in enumerate(LINES)],
        )
        conn.execute(
            s.products.insert(),
            [
                {
                    "id": i * 3 + j + 1,
                    "name": n + ["标准版", "专业版", "企业版"][j],
                    "product_line_id": i + 1,
                }
                for i, n in enumerate(LINES)
                for j in range(3)
            ],
        )
        conn.execute(
            s.customers.insert(),
            [
                {
                    "id": i,
                    "name": f"模拟·{['远川', '启衡', '澄岳', '景禾', '明瀚'][i % 5]}{INDUSTRIES[(i - 1) % 6]}集团{i:04d}",
                    "industry_id": (i - 1) % 6 + 1,
                }
                for i in range(1, 1001)
            ],
        )
        conn.execute(
            s.salespeople.insert(),
            [
                {"id": i, "name": f"销售顾问{i:02d}", "org_unit_id": (i - 1) // 6 + 1}
                for i in range(1, 61)
            ],
        )
        contracts = []
        items = []
        revenue = []
        cost = []
        payments = []
        targets = []
        for mi in range(32):
            year, month = divmod(2024 * 12 + mi, 12)
            month += 1
            growth = 1 + 0.10 * (year - 2024)
            season = {1: 0.65, 2: 0.48, 3: 1.2, 6: 1.4, 9: 1.35, 11: 1.2, 12: 1.7}.get(
                month, 1
            )
            for oi in range(1, 11):
                for pi in range(1, 6):
                    # Monthly planning grain is deliberately independent of contract lines.
                    target = cents(
                        850000
                        * [1.35, 1.3, 1.05, 1, 0.8, 1.1, 1.25, 0.85, 0.8, 0.65][oi - 1]
                        * [1.1, 1.2, 0.9, 0.7, 0.65][pi - 1]
                        * growth
                        * season
                    )
                    targets.append(
                        {
                            "month": date(year, month, 1),
                            "org_unit_id": oi,
                            "product_line_id": pi,
                            "revenue_target": target,
                        }
                    )
            count = round(150 * season * growth)
            for _ in range(count):
                cid = len(contracts) + 1
                oi = rng.choices(
                    range(1, 11), weights=[14, 14, 10, 10, 8, 10, 12, 8, 8, 6]
                )[0]
                signed = date(
                    year, month, rng.randint(1, calendar.monthrange(year, month)[1])
                )
                customer = (
                    rng.randint(1, 120)
                    if rng.random() < 0.48
                    else rng.randint(121, 1000)
                )
                cancelled = rng.random() < 0.025
                contracts.append(
                    {
                        "id": cid,
                        "number": f"HT-{year}-{cid:05d}",
                        "customer_id": customer,
                        "org_unit_id": oi,
                        "salesperson_id": (oi - 1) * 6 + rng.randint(1, 6),
                        "signed_date": signed,
                        "status": "cancelled" if cancelled else "active",
                    }
                )
                amount_total = Decimal(0)
                for _ in range(rng.choices([1, 2, 3], [0.55, 0.35, 0.1])[0]):
                    pi = rng.choices(range(1, 6), weights=[25, 26, 20, 15, 14])[0]
                    amount = cents(
                        min(3500000, max(25000, rng.lognormvariate(12.2, 0.8))) * growth
                    )
                    if year == 2026 and oi in [2, 3, 4] and pi == 2:
                        amount = cents(amount * Decimal("1.4"))
                    iid = len(items) + 1
                    items.append(
                        {
                            "id": iid,
                            "contract_id": cid,
                            "product_id": (pi - 1) * 3 + rng.randint(1, 3),
                            "amount_ex_tax": amount,
                        }
                    )
                    amount_total += amount
                    if cancelled:
                        continue
                    installments = 3 if pi in [2, 3, 5] else 2
                    allocated = Decimal(0)
                    for step in range(installments):
                        dt = shift(signed, step + 1)
                        value = (
                            amount - allocated
                            if step == installments - 1
                            else cents(amount / installments)
                        )
                        allocated += value
                        if dt > CUTOFF:
                            continue
                        revenue.append(
                            {
                                "contract_item_id": iid,
                                "recognition_date": dt,
                                "amount_ex_tax": value,
                            }
                        )
                        ratio = [0.40, 0.48, 0.60, 0.42, 0.72][pi - 1] + rng.uniform(
                            -0.06, 0.06
                        )
                        if year == 2026 and oi in [2, 3, 4] and pi == 2:
                            ratio += 0.13
                        cost.append(
                            {
                                "contract_item_id": iid,
                                "cost_date": dt,
                                "amount_ex_tax": cents(value * Decimal(str(ratio))),
                            }
                        )
                if not cancelled:
                    first = cents(amount_total * Decimal(".3"))
                    payments.append(
                        {
                            "contract_id": cid,
                            "payment_date": signed,
                            "amount_ex_tax": first,
                        }
                    )
                    delayed = rng.random() < 0.16
                    dt = shift(signed, 6 if delayed else 3)
                    if dt <= CUTOFF:
                        payments.append(
                            {
                                "contract_id": cid,
                                "payment_date": dt,
                                "amount_ex_tax": amount_total - first,
                            }
                        )
        datasets = [
            (s.contracts, contracts),
            (s.contract_items, items),
            (s.revenue_entries, revenue),
            (s.cost_entries, cost),
            (s.payment_entries, payments),
            (s.monthly_targets, targets),
        ]
        for tbl, rows in datasets:
            for offset in range(0, len(rows), 1000):
                conn.execute(tbl.insert(), rows[offset : offset + 1000])
        if not conn.scalar(select(s.users.c.id).where(s.users.c.username == "admin")):
            conn.execute(
                s.users.insert().values(
                    username="admin",
                    display_name="管理员",
                    password_hash=hash_password(settings().admin_password),
                    role="admin",
                )
            )
        conn.execute(
            s.metric_definitions.insert(),
            [
                {
                    "code": k,
                    "name": v["name"],
                    "version": 1,
                    "definition": {**v, "dimensions": DIMENSIONS},
                }
                for k, v in METRICS.items()
            ],
        )
        for tbl in [
            s.org_units,
            s.industries,
            s.product_lines,
            s.products,
            s.customers,
            s.salespeople,
            s.contracts,
            s.contract_items,
        ]:
            conn.execute(
                __import__("sqlalchemy").text(
                    f"SELECT setval(pg_get_serial_sequence('{tbl.fullname}', 'id'), (SELECT MAX(id) FROM {tbl.fullname}))"
                )
            )
        counts = {tbl.name: len(rows) for tbl, rows in datasets}
        counts.update(
            {
                "customers": 1000,
                "org_units": 10,
                "products": 15,
                "product_lines": 5,
                "industries": 6,
                "salespeople": 60,
            }
        )
        conn.execute(
            s.dataset_versions.insert().values(
                version=VERSION,
                seed=SEED,
                start_date=START,
                cutoff_date=CUTOFF,
                counts=counts,
            )
        )
    return {"status": "seeded", "counts": counts}


if __name__ == "__main__":
    print(seed())
