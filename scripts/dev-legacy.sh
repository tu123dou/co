#!/bin/sh
# 旧嵌入式 PostgreSQL 开发入口，仅用于旧环境维护。
set -eu
echo '注意：此脚本启动旧嵌入式数据库并执行迁移初始化；当前项目请优先使用 docker compose up -d --build。' >&2
cd "$(dirname "$0")/.."
mkdir -p .runtime
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; .venv/bin/pip install -r backend/requirements.lock; fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm ci); fi
if [ ! -d .runtime/pg-tools/node_modules/embedded-postgres ]; then npm install --prefix .runtime/pg-tools embedded-postgres@18.1.0-beta.15; fi
python3 scripts/setup-env.py
node scripts/local-postgres.mjs > .runtime/postgres.log 2>&1 &
pg_pid=$!
api_pid=''
web_pid=''
cleanup() { [ -z "$web_pid" ] || kill "$web_pid" 2>/dev/null || true; [ -z "$api_pid" ] || kill "$api_pid" 2>/dev/null || true; kill "$pg_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
PYTHONPATH=backend .venv/bin/python scripts/wait-db.py
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/python scripts/grant-query.py
PYTHONPATH=backend .venv/bin/python -m app.seed
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > .runtime/backend.log 2>&1 &
api_pid=$!
(cd frontend && VITE_API_PROXY=http://127.0.0.1:8000 exec npm run dev) &
web_pid=$!
echo 'Open http://127.0.0.1:5881 ; username admin, password is ADMIN_PASSWORD in .env'
wait "$web_pid"
