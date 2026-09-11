"""Run after migrations as schema owner; never grants access to application tables."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.db import engine
from app.config import settings

role = make_url(settings().query_database_url).username
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
