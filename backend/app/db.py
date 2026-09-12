"""数据库连接池。

engine 使用 app 账号，负责用户、对话和审计等正常读写；query_engine 使用 analyst
账号，只执行问数 SQL。两个账号在 PostgreSQL 中权限不同，即使应用校验遗漏，
analyst 也不能修改表或读取 app 模式数据。
"""

from sqlalchemy import create_engine
from .config import settings

engine = create_engine(
    settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5
)
# 查询编译结果仅通过 analyst 账号执行，权限由数据库侧限制为只读。
query_engine = create_engine(
    settings().query_database_url, pool_pre_ping=True, pool_size=3, max_overflow=3
)
