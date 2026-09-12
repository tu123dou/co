#!/bin/sh
# PostgreSQL 容器首次启动时创建应用账号、只读问数账号和 pgvector 扩展。
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$APP_DB_PASSWORD" --set=query_password="$QUERY_DB_PASSWORD" <<'SQL'
CREATE ROLE app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE analyst LOGIN PASSWORD :'query_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER DATABASE jingguan OWNER TO app;
GRANT CREATE ON SCHEMA public TO app;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
