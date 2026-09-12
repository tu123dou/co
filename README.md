# 经管之星 · AI 智能问数

React + Python + PostgreSQL 的本地经营分析工作台。真实调用百炼 qwen3.8-max，业务数据为固定种子生成的虚构企业软件与服务台账。没有规则模拟模型或写死问数答案。

## 云服务器部署（暂未配置域名）

前端镜像已经内置 Nginx，并会把 `/api` 转发到后端，因此无需在宿主机重复安装 Nginx。以公网 IP `8.137.78.125` 直接提供 HTTP 服务时，在服务器 `.env` 中设置：

```dotenv
COOKIE_SECURE=false
ALLOWED_ORIGIN=http://8.137.78.125
APP_BIND_ADDRESS=0.0.0.0
APP_PORT=80
```

然后启动并检查服务：

```bash
cd /opt/ai-wenshu/co
docker compose up -d --build
docker compose ps
curl http://127.0.0.1/api/health
```

阿里云安全组只需放行公网 TCP 80；PostgreSQL 仍只监听服务器本机的 `127.0.0.1:54330`。以后配置域名和 HTTPS 时，将 `ALLOWED_ORIGIN` 改成实际 HTTPS 域名并设置 `COOKIE_SECURE=true`。

## 当前机器访问

- 网站：http://127.0.0.1:5178/
- API 文档：http://127.0.0.1:8000/docs
- 用户名：`admin`
- 密码：项目根目录 `.env` 的 `ADMIN_PASSWORD`。
- API Key 已保存在本地 `.env`；修改后重启后端。不要提交或公开该文件。

## 本地启动（OrbStack）

推荐使用 OrbStack 运行正式的本地开发栈，数据库镜像为 `pgvector/pgvector:0.8.6-pg18-trixie`。

```sh
python3 scripts/setup-env.py
docker compose up --build -d
```

访问 `http://127.0.0.1:5178`。PostgreSQL 仅映射到本机 `127.0.0.1:54330`，数据保存在 Compose 命名卷中。后端启动时运行 Alembic、初始化模拟数据，并用百炼 `qwen3.7-text-embedding-flash` 同步 1024 维业务语义目录。

- 初始化脚本发现数据版本存在时直接退出，绝不覆盖已有业务数据。
- `.env` 中的初始登录密码仅用于首次创建账号，之后修改环境变量不会自动重置已有密码。
- 不要运行 `docker compose down -v`，除非确实要删除整个容器数据库。

原 embedded-postgres 数据迁移时，先保持旧库运行并执行：

```sh
PYTHONPATH=backend .venv/bin/python scripts/transfer-data.py export .runtime/pre-orbstack-backup.jsonl.gz
# 启动并迁移容器数据库后：
PYTHONPATH=backend .venv/bin/python scripts/transfer-data.py import .runtime/pre-orbstack-backup.jsonl.gz
```

备份和导入都会核对逐表记录数；目标库存在业务数据时导入会拒绝覆盖。旧 embedded-postgres 数据目录仅作为迁移来源保留，正常开发以 OrbStack 为准。

`.env.example` 中 `${...}` 是生成占位符，请使用脚本而非直接复制后启动。

云端公开部署前需配置域名、HTTPS、`COOKIE_SECURE=true`、正确的 `ALLOWED_ORIGIN`，并配置备份和入口限流；当前配置只对本机开放。

## 功能范围

- 登录、会话归属隔离、历史记录、置顶、重命名、删除。
- 自然语言查询、连续追问、澄清、不支持问题提示、停止、重试。
- 收入、签约额、回款额、直接成本、毛利、毛利率、收入目标达成率。
- 汇总、排名、月份趋势、维度拆分、同比、环比。
- 指标卡、折线/柱状/占比图、数据表、当前展示结果 CSV 导出。
- 指标口径、参数化 SQL、数据版本、查询耗时可追溯。
- 收藏、回答反馈、模型连接测试。

每次问数由模型解释为受约束的结构化计划，程序校验后编译 SQL。金额及同比计算来自数据库和 Decimal 运算；中文结论使用可核对的确定性模板生成，避免模型补写数字。图表来自同一结果集。推荐追问来自业务规则。

未实现：任意 SQL 编辑、跨数据源接入、文件上传、自由因果归因、金额区间筛选、订单数量、任意逐笔财务流水、商机/PPL、项目风险、产品线回款分摊和反馈管理后台。已支持受控的客户合同清单、单笔应收计划排行、经营预测和应收分析。未知能力会明确提示，不静默替换查询。用户共享业务数据，个人会话、收藏和工作台设置等应用数据相互隔离。

## 数据与口径

13 张业务表、14 张应用表，分 `analytics` 与 `app` 两个 schema；Alembic 另有迁移版本表。业务域包含合同、产品、收入、成本、回款、应收和经营预测；应用域增加用户独立的工作台设置与常见问题统计。业务数据覆盖 2024-01-01 至 2026-08-31，种子 `20260912`。

实际生成：1,756 份合同、2,719 条合同明细、6,179 条收入确认、6,179 条成本、3,184 条回款、3,420 条应收计划和1,600条月度目标，另有1,000家客户及组织/产品等维度数据。

- 金额全部是不含税管理金额；回款为管理折算金额，不用于财务报税。
- 收入分期确认，成本与确认期匹配；回款有预付款及正常/延期尾款。
- 收入累计不超过合同明细金额，回款累计不超过合同金额；取消合同不计入指标。
- 相对时间以数据截止日为参考。“今年”默认 2026-01-01 至 2026-08-31；明确指定超出覆盖范围时拒绝查询。
- 同比使用去年相同日期范围；整月/整季度环比按日历月回退，其他日期区间按等长天数回退。
- 毛利率使用总收入和总成本计算，不平均分组百分比。目标和收入分别聚合，避免目标重复累计。
- 达成率只支持完整月份，且不支持未分配目标的客户、行业或销售人员维度。
- 回款在合同粒度，不支持产品线维度。一次最多返回 500 个分组；展示前 1–100 组，汇总仍包含全部符合条件数据。
- 模拟数据按通用计算、智能计算、数据存储、商业解决方案及交付维保生成，并包含项目交付和应收风险；这只是演示机制，不是对真实企业的判断。

## 开发与验证

```sh
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
TEST_DATABASE=1 PYTHONPATH=backend .venv/bin/pytest backend/tests -q
cd frontend && npm run build
```

数据库集成测试只创建并清理专属测试账号，会验证数据库权限、金额独立核对、会话隔离、导出、反馈及收藏。不要指向未经确认的生产库运行测试。

真实模型评估会消耗 API 额度：

```sh
.venv/bin/python scripts/evaluate.py
```

报告见 `docs/model-evaluation.json`。评估通过代表这些固定问题的指标、维度、对比方式及执行路径通过；不代表任意自然语言问题都能100%正确理解。数值正确性由独立数据库测试核对。

## 项目结构

- `backend/app/semantic.py`：版本化指标字典、查询计划 Schema。
- `backend/app/query.py`：只读 SQL 编译、校验及数值计算。
- `backend/app/llm.py`：百炼兼容接口、模型结果校验及有限重试。
- `backend/app/retrieval.py`：业务目录生成、向量同步、精确词面匹配与 pgvector 召回。
- `backend/app/main.py`：认证、会话、流式问数与辅助 API。
- `backend/app/schema.py`：27 张领域表结构；`alembic/`：冻结迁移。
- `backend/app/seed.py`：可重复、不可覆盖的模拟数据生成器。
- `frontend/src/Workbench.tsx`：问数工作台与结果展示。
- `docs/architecture.md`：执行边界与后续扩展。

模型仅接收召回的业务目录、合法实体值、用户问题和近期上下文，不获得数据库账号或 API Key。pgvector 只选择相关指标、维度、表字段、实体和示例；模型仍只生成受 Pydantic 约束的计划，SQL 由程序编译并经 SQLGlot 校验。第一版直接使用 SQLAlchemy + pgvector，不引入 LlamaIndex。
