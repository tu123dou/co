"""数据库授权脚本：迁移后仅向 analyst 账号授予 analytics 查询权限。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.db import engine
from app.config import settings

role = make_url(settings().query_database_url).username
# 角色名来自受信任配置，但仍按 PostgreSQL 标识符规则转义。
quoted = '"' + role.replace('"', '""') + '"'
with engine.begin() as conn:
    conn.execute(text("REVOKE ALL ON SCHEMA analytics FROM PUBLIC"))
    conn.execute(text("REVOKE ALL ON SCHEMA app FROM PUBLIC"))
    conn.execute(text("GRANT USAGE ON SCHEMA analytics TO " + quoted))
    conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO " + quoted))
    conn.execute(
        text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO "
            + quoted
        )
    )
print("Analyst granted SELECT on analytics only.")
