"""数据库就绪检查：开发环境启动时最多等待 PostgreSQL 三十秒。"""

import time
from sqlalchemy import text
from app.db import engine

for _ in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Database did not start. Check .runtime/postgres.log")
