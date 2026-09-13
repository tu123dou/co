"""演示业务数据初始化模块。

它按固定随机种子生成接近算力基础设施销售场景的组织、客户、产品、合同、收入、
成本、回款、月度目标和应收计划。固定种子保证每次全新初始化得到相同数据，方便
演示结果复现；发现已有业务数据时会拒绝覆盖。
"""

import calendar, random
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from . import schema as s
from .db import engine
from .config import settings
from .auth import hash_password
from .semantic import METRICS, DIMENSIONS

SEED = 20260912
START = date(2024, 1, 1)
CUTOFF = date(2026, 8, 31)
VERSION = "synthetic-computing-v2"
ORG = [
    ("OU-BJ", "北京代表处", "代表处", "华北", "北京"),
    ("OU-SH", "上海代表处", "代表处", "华东", "上海"),
    ("OU-ZJ", "浙江代表处", "代表处", "华东", "杭州"),
    ("OU-JS", "江苏代表处", "代表处", "华东", "南京"),
    ("OU-SD", "山东代表处", "代表处", "华北", "济南"),
    ("OU-GZ", "广州代表处", "代表处", "华南", "广州"),
    ("OU-SZ", "深圳代表处", "代表处", "华南", "深圳"),
    ("OU-CZ", "川藏代表处", "代表处", "西南", "成都"),
    ("OU-HB", "湖北办事处", "办事处", "华中", "武汉"),
    ("OU-SX", "陕西办事处", "办事处", "西北", "西安"),
]
LINES = [("GENERAL", "通用计算"), ("AI", "智能计算"), ("STORAGE", "数据存储"), ("SOLUTION", "商业解决方案"), ("SERVICE", "交付与维保")]
PRODUCTS = [
    ("TG225-A1", "凌云通用服务器", "TG225 A1"), ("TG225-B1", "凌云高密服务器", "TG225 B1"), ("TG223-B1", "凌云边缘服务器", "TG223 B1"),
    ("AT3500-G3", "天智推理服务器", "AT3500 G3"), ("AT9508-G3", "天智训推一体服务器", "AT9508 G3"), ("AT800-9000", "天智训练服务器", "AT800 9000"),
    ("ST5500", "全闪数据存储", "ST5500"), ("ST6800", "分布式数据存储", "ST6800"), ("BK3000", "备份一体机", "BK3000"),
    ("SOL-AICC", "智算中心集成方案", "AICC"), ("SOL-AGENT", "企业智能体一体机", "AgentBox"), ("SOL-RESEARCH", "AI科研一体机", "ResearchBox"),
    ("SVC-DELIVERY", "集成交付服务", "Delivery"), ("SVC-MAINT", "年度维保服务", "Maintenance"), ("SVC-OPT", "算力集群优化服务", "Optimization"),
]
INDUSTRIES = [("TELCO", "运营商"), ("FIN", "金融"), ("GOV", "数字政府"), ("EDU", "教育科研"), ("MFG", "智能制造"), ("OTHER", "交通医疗电力")]


def shift(d, months):
    idx = d.year * 12 + d.month - 1 + months
    y, m = divmod(idx, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def cents(amount):
    return Decimal(str(amount)).quantize(Decimal(".01"))


def seed():
    """只初始化一次内部口径一致、可重复生成的演示数据集。"""
    rng = random.Random(SEED)
    with engine.begin() as conn:
        conn.execute(
            __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(9260911)")
        )
        # 事务级 advisory lock 防止多个启动进程同时初始化数据。
        if conn.scalar(select(func.count()).select_from(s.dataset_versions)):
            return {"status": "already_seeded"}
        if conn.scalar(select(func.count()).select_from(s.contracts)):
            raise RuntimeError("Existing business data found; refusing to overwrite")
        conn.execute(
            s.org_units.insert(),
            [
                {"id": i + 1, "code": code, "name": n, "unit_type": typ, "region": r, "city": c}
                for i, (code, n, typ, r, c) in enumerate(ORG)
            ],
        )
        conn.execute(
            s.industries.insert(),
            [{"id": i + 1, "code": code, "name": n} for i, (code, n) in enumerate(INDUSTRIES)],
        )
        conn.execute(
            s.product_lines.insert(),
            [{"id": i + 1, "code": code, "name": n} for i, (code, n) in enumerate(LINES)],
        )
        conn.execute(
            s.products.insert(),
            [
                {
                    "id": i + 1, "code": code, "name": name, "model": model,
                    "product_line_id": i // 3 + 1,
                }
                for i, (code, name, model) in enumerate(PRODUCTS)
            ],
        )
        conn.execute(
            s.customers.insert(),
            [
                {
                    "id": i,
                    "code": f"CUS-{i:05d}",
                    "name": f"{['远川', '启衡', '澄岳', '景禾', '明瀚'][i % 5]}{INDUSTRIES[(i - 1) % 6][1]}集团{i:04d}",
                    "province": ["北京", "上海", "浙江", "江苏", "山东", "广东", "四川", "湖北", "陕西"][i % 9],
                    "industry_id": (i - 1) % 6 + 1,
                }
                for i in range(1, 1001)
            ],
        )
        conn.execute(
            s.salespeople.insert(),
            [
                {"id": i, "code": f"EMP-{i:04d}", "name": f"客户经理{i:02d}", "org_unit_id": (i - 1) // 6 + 1}
                for i in range(1, 61)
            ],
        )
        contracts = []
        items = []
        revenue = []
        cost = []
        payments = []
        targets = []
        receivables = []
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
                            "floor_amount": cents(target * Decimal("0.82")),
                            "forecast_amount": cents(target * Decimal(str(rng.uniform(0.78, 1.08)))),
                        }
                    )
            count = round(48 * season * growth)
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
                # Keep one unambiguous contract customer while preserving the
                # former analytical customer choice and random sequence.
                if customer % 7 == 0:
                    customer = rng.randint(121, 1000)
                salesperson = (oi - 1) * 6 + rng.randint(1, 6)
                primary_line = rng.choices(range(1, 6), weights=[38, 31, 10, 15, 6])[0]
                primary_product = (primary_line - 1) * 3 + rng.randint(1, 3)
                cancelled = rng.random() < 0.025
                # Preserve the original random sequence for stable contract data.
                rng.random()
                rng.randint(2, 80)
                rng.uniform(800000, 12000000)
                contracts.append(
                    {
                        "id": cid,
                        "number": f"HT-{year}-{cid:05d}",
                        "name": f"算力产品采购及服务合同{cid:04d}",
                        "customer_id": customer,
                        "org_unit_id": oi,
                        "salesperson_id": salesperson,
                        "signed_date": signed,
                        "status": "cancelled" if cancelled else "active",
                    }
                )
                amount_total = Decimal(0)
                for item_no in range(rng.choices([1, 2, 3], [0.55, 0.35, 0.1])[0]):
                    pi = primary_line if item_no == 0 else rng.choices(range(1, 6), weights=[38, 31, 10, 15, 6])[0]
                    amount = cents(
                        min(80000000, max(300000, rng.lognormvariate(14.6, 1.0))) * growth
                    )
                    if year == 2026 and oi in [2, 3, 4] and pi == 2:
                        amount = cents(amount * Decimal("1.4"))
                    iid = len(items) + 1
                    quantity = rng.randint(1, 120)
                    items.append(
                        {
                            "id": iid,
                            "contract_id": cid,
                            "product_id": primary_product if item_no == 0 else (pi - 1) * 3 + rng.randint(1, 3),
                            "quantity": quantity, "unit_name": "台" if pi <= 3 else "套",
                            "tax_rate": Decimal("0.13") if pi <= 3 else Decimal("0.06"),
                            "amount_ex_tax": amount,
                            "amount_with_tax": cents(amount * (Decimal("1.13") if pi <= 3 else Decimal("1.06"))),
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
                    receivables.append({"contract_id": cid, "due_date": signed, "amount_ex_tax": first, "settled_amount_ex_tax": first, "status": "已结清"})
                    delayed = rng.random() < 0.16
                    dt = shift(signed, 6 if delayed else 3)
                    balance = amount_total - first
                    collected = dt <= CUTOFF and rng.random() >= (0.18 if delayed else 0.06)
                    if collected:
                        payments.append(
                            {
                                "contract_id": cid,
                                "payment_date": dt,
                            "amount_ex_tax": balance,
                            }
                        )
                    settled = balance if collected else Decimal("0")
                    receivables.append({"contract_id": cid, "due_date": dt, "amount_ex_tax": balance, "settled_amount_ex_tax": settled, "status": "已结清" if settled else "逾期" if dt < CUTOFF else "待收"})
        datasets = [
            (s.contracts, contracts),
            (s.contract_items, items),
            (s.revenue_entries, revenue),
            (s.cost_entries, cost),
            (s.payment_entries, payments),
            (s.monthly_targets, targets),
            (s.receivable_entries, receivables),
        ]
        for tbl, rows in datasets:
            for offset in range(0, len(rows), 1000):
                conn.execute(tbl.insert(), rows[offset : offset + 1000])
        if not conn.scalar(select(s.users.c.id).where(s.users.c.username == "admin")):
            conn.execute(
                s.users.insert().values(
                    username="admin",
                    display_name="演示用户",
                    is_superuser=True,
                    password_hash=hash_password(settings().admin_password),
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
            s.receivable_entries,
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
