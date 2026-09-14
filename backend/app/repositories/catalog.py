"""数据范围、标准实体目录及实体校验。"""

from sqlalchemy import select

from .. import schema as s
from ..contracts import DatasetInfo, QueryPlan
from ..db import engine
from ..errors import ServiceUnavailable


def dataset_info() -> DatasetInfo:
    """读取当前演示数据版本以及可查询的起止日期。"""
    with engine.connect() as conn:
        d = (
            conn.execute(
                select(s.dataset_versions).order_by(s.dataset_versions.c.id.desc())
            )
            .mappings()
            .first()
        )
    if not d:
        raise ServiceUnavailable("请先初始化业务数据")
    return dict(d)


def get_catalog():
    """读取标准筛选值，供受控查询规划器解析实体名称。"""
    with engine.connect() as conn:
        catalog = {
            "region": list(conn.scalars(select(s.org_units.c.region).distinct())),
            "city": list(conn.scalars(select(s.org_units.c.city))),
            "org_unit": list(conn.scalars(select(s.org_units.c.name))),
            "industry": list(conn.scalars(select(s.industries.c.name))),
            "product_line": list(conn.scalars(select(s.product_lines.c.name))),
            "salesperson": list(conn.scalars(select(s.salespeople.c.name))),
        }
    return catalog


def validate_filters(plan: QueryPlan, catalog: dict[str, list[str]]) -> None:
    """确认模型生成的筛选值能匹配真实业务实体。"""
    for f in plan.filters:
        if f.dimension == "month":
            import re

            if any(not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", v) for v in f.values):
                raise ValueError("月份格式需为 YYYY-MM")
        elif f.dimension == "customer":
            with engine.connect() as conn:
                found = set(
                    conn.scalars(
                        select(s.customers.c.name).where(
                            s.customers.c.name.in_(f.values)
                        )
                    )
                )
            if set(f.values) - found:
                raise ValueError("未找到该客户，请使用完整客户名称")
        elif set(f.values) - set(catalog[f.dimension]):
            raise ValueError(
                "未找到筛选值：" + ", ".join(set(f.values) - set(catalog[f.dimension]))
            )
