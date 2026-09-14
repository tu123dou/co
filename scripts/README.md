# 脚本用途

脚本是显式执行的运维或验证入口，未被前端导入不代表无用。

| 文件 | 用途 |
| --- | --- |
| `setup-env.py` | 首次生成本地环境配置，保留已有配置 |
| `docker-init.sh` | Compose 数据库首次初始化入口 |
| `grant-query.py` | 后端容器启动时授予只读查询权限 |
| `transfer-data.py` | 数据导出、恢复及旧环境迁移 |
| `evaluate.py` | 显式运行真实模型评估，产生 API 费用 |
| `retest-failed.py` | 对评估报告中的失败案例复测，产生 API 费用 |
| `smoke-orbstack.py` | 对本地完整服务运行真实问数冒烟，产生 API 费用 |
| `dev-legacy.sh`、`local-postgres.mjs`、`wait-db.py` | 旧嵌入式 PostgreSQL 开发入口，保留用于旧环境维护；前端固定代理本机 8000 端口 |

当前推荐启动方式为仓库根目录的 `docker compose up --build -d`。前端热更新可通过 `cd frontend && VITE_API_PROXY=http://127.0.0.1:5178 npm run dev` 连接本地 Compose 服务，访问端口为 5881。

旧开发入口会启动另一套数据库、执行迁移和初始化，不要与现有环境混用。数据库迁移、初始化和模型评估不属于普通前端构建步骤。
