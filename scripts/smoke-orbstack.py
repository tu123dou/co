"""OrbStack 冒烟脚本：向本地完整服务发送一条真实端到端问题。"""

import json

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from app import schema as s
from app.config import settings


def main():
    cfg = settings()
    question = "华东区今年各产品线确认收入"
    conversation_id = None
    with httpx.Client(base_url="http://127.0.0.1:5178", timeout=120) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": cfg.admin_password},
        )
        login.raise_for_status()
        try:
            conversation_id = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{conversation_id}/ask",
                json={"question": question},
            )
            response.raise_for_status()
            events = [json.loads(line) for line in response.text.splitlines()]
            final = events[-1]["message"]["result"]
            if final["status"] != "success" or final["plan"]["metric"] != "revenue":
                raise RuntimeError(f"unexpected answer: {final}")

            target_url = make_url(cfg.database_url).set(host="127.0.0.1", port=54330)
            target = create_engine(target_url)
            with target.connect() as conn:
                audit = (
                    conn.execute(
                        select(s.retrieval_events)
                        .where(s.retrieval_events.c.question == question)
                        .order_by(s.retrieval_events.c.created_at.desc())
                    )
                    .mappings()
                    .first()
                )
            if not audit:
                raise RuntimeError("missing retrieval audit")
            exact_titles = [hit["title"] for hit in audit["hits"] if hit.get("match") == "exact"]
            print(
                json.dumps(
                    {
                        "status": final["status"],
                        "metric": final["plan"]["metric"],
                        "rows": len(final["rows"]),
                        "exact_retrieval": exact_titles,
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            if conversation_id:
                client.delete(f"/api/conversations/{conversation_id}").raise_for_status()


if __name__ == "__main__":
    main()
