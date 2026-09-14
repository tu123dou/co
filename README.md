# 经管之星 · AI 智能问数

React + Python + PostgreSQL 的本地经营分析工作台。经营查询真实调用百炼模型，业务数据为固定种子生成的虚构企业软件与服务台账；助手介绍和业务数据说明由可信目录生成。

## 云服务器部署（暂未配置域名）

登录服务器 workbench connect -i i-2vcgdfqug0vm5icpp2nm
cd /opt/ai-wenshu/co

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

首次初始化或业务目录变化后，单独同步一次向量索引：

```bash
docker compose run --rm backend python -m app.retrieval sync
```

向量同步失败不会阻止后端启动，问数会暂时使用内置业务目录继续工作。

阿里云安全组只需放行公网 TCP 80；PostgreSQL 仍只监听服务器本机的 `127.0.0.1:54330`。以后配置域名和 HTTPS 时，将 `ALLOWED_ORIGIN` 改成实际 HTTPS 域名并设置 `COOKIE_SECURE=true`。

## 当前机器访问

- 网站：http://127.0.0.1:5178/
- API 文档：直接启动本机后端时为 http://127.0.0.1:8000/docs；Compose 默认不映射后端端口。
- 用户名：`admin`
- 密码：项目根目录 `.env` 的 `ADMIN_PASSWORD`。
- API Key 已保存在本地 `.env`；修改后重启后端。不要提交或公开该文件。

## 本地启动（OrbStack）

推荐使用 OrbStack 运行正式的本地开发栈，数据库镜像为 `pgvector/pgvector:0.8.6-pg18-trixie`。

```sh
python3 scripts/setup-env.py
docker compose up --build -d
```

访问 `http://127.0.0.1:5178`。PostgreSQL 仅映射到本机 `127.0.0.1:54330`，数据保存在 Compose 命名卷中。后端启动时只运行 Alembic 和数据初始化，不再等待外部向量服务；需要重建语义目录时执行上面的独立同步命令。

只启动本地前端并代理云端 API：

```sh
cd frontend
VITE_API_PROXY=http://8.137.78.125 npm run dev
```

浏览器访问 `http://127.0.0.1:5881`，页面的 `/api` 请求会由 Vite 转发到云端。

- 初始化脚本发现数据版本存在时直接退出，绝不覆盖已有业务数据。
- `.env` 中的初始登录密码仅用于首次创建账号，之后修改环境变量不会自动重置已有密码。
- 不要运行 `docker compose down -v`，除非确实要删除整个容器数据库。

旧嵌入式开发入口为 `sh scripts/dev-legacy.sh`，只用于旧环境维护，不是当前推荐的启动方式；该入口固定代理本机 8000 端口，不会读取云端代理目标。

原 embedded-postgres 数据迁移时，先保持旧库运行并执行：

```sh
PYTHONPATH=backend .venv/bin/python scripts/transfer-data.py export .runtime/pre-orbstack-backup.jsonl.gz
# 启动并迁移容器数据库后：
PYTHONPATH=backend .venv/bin/python scripts/transfer-data.py import .runtime/pre-orbstack-backup.jsonl.gz
```

备份和导入都会核对逐表记录数；目标库存在业务数据时导入会拒绝覆盖。旧 embedded-postgres 数据目录仅作为迁移来源保留，正常开发以 OrbStack 为准。

`.env.example` 中 `${...}` 是生成占位符，请使用脚本而非直接复制后启动。

云端公开部署前需配置域名、HTTPS、`COOKIE_SECURE=true`、正确的 `ALLOWED_ORIGIN`，并配置备份和入口限流；默认绑定本机，实际绑定以 `.env` 的 `APP_BIND_ADDRESS` 为准。

## 功能范围

### 自定义问数模型

应用配置 → 模型配置 → 新增模型，可选择 OpenAI Chat Completions 或 Anthropic Messages 格式，填写请求地址、模型 ID、可选展示名称和 API 密钥。默认基础 URL 模式：OpenAI 补充 `/chat/completions`，Anthropic 补充 `/v1/messages`（基础地址已以 `/v1` 结尾则仅补充 `/messages`）；开启“完整 URL”后直接使用所填地址，不拼接路径。已有配置默认按完整 URL 处理。展示名称为空时使用模型 ID。测试连接后添加（测试非强制），选中并保存后用于当前用户的问数。添加不会修改当前选用模型，取消模型配置也不会删除已添加的条目。每人最多 20 个自定义配置，同协议、最终请求地址和模型 ID 不允许重复。模型仍须输出符合受控查询计划的 JSON；连通测试不等于查询计划兼容性验证。

模型下拉选项右侧可编辑或删除自己的自定义模型；编辑时密钥留空保留原密钥，填写新密钥则替换，连接测试不会保存编辑。删除需要确认，若删除当前使用的模型，恢复默认内置模型，不影响历史会话。密钥输入采用非密码表单和视觉遮罩，避免触发浏览器保存密码提示；第三方密码管理器可能有独立行为。

后端须先安装依赖并运行 Alembic `upgrade head`（Compose 启动会自动执行）。`0013` 增加用户模型配置；`0014` 将已有 Base URL 配置转换为完整 OpenAI 请求地址并补充协议与展示名称，不改变模型 ID、选择状态和密钥密文。API Key 使用 `cryptography` 的 Fernet 认证加密入库，接口不返回密钥或密文。推荐配置独立的 `MODEL_ENCRYPTION_SECRET`（至少 32 字符）；留空时从 JWT_SECRET 按用途和用户派生。必须备份并稳定保留加密密钥，轮换前需迁移密文，否则已有配置不能解密。

自定义模型不再使用供应商 URL 白名单或 IP 范围限制，旧 `CUSTOM_MODEL_BASE_URLS` 配置不再生效。支持内网、回环和保留地址的完整 HTTPS URL，不接受 URL 中的账号、查询参数或片段，保留证书校验，禁止重定向和环境代理。登录用户可以让后端访问其网络可达的服务，因此仅应向可信用户开放，并仅填写可信模型服务地址。Docker 中的 localhost/127.0.0.1 指向后端容器自身，而非宿主机。不要在公网 HTTP 页面填写真实密钥，应先配置 HTTPS 或使用 SSH 隧道访问本地页面。

内置模型仍使用服务端凭据；向量、语音接口不随自定义问数模型切换。新增、连通测试和选择仅对当前登录用户生效。

- 登录、会话归属隔离、历史记录、置顶、重命名、删除。
- 自然语言查询、连续追问、澄清、不支持问题提示、停止、重试。
- 助手介绍、业务表数量与用途、字段说明、数据日期范围、能力范围、指标口径、分析维度与数据来源说明；只向问数用户展示业务表。
- 收入、签约额、回款额、直接成本、毛利、毛利率、收入目标达成率。
- 汇总、排名、月份趋势、维度拆分、同比、环比。
- 指标卡、折线/柱状/占比图、数据表、当前展示结果 CSV 导出。
- 指标口径、参数化 SQL、数据版本、查询耗时可追溯。
- 收藏、回答反馈、回复校对管理、模型连接测试。

经营查询由模型解释为受约束的结构化计划，程序校验后编译 SQL。金额及同比计算来自数据库和 Decimal 运算；中文结论使用可核对的确定性模板生成，避免模型补写数字。图表来自同一结果集。推荐追问来自业务规则。

“你是谁”“有多少个数据表”“数据日期范围”“每个数据表是什么”等常见说明问题直接回答，不调用模型或向量服务；其他表达由模型识别为受约束的说明请求，再由业务白名单、目录和当前数据版本生成答案。说明回答保存到历史，但不覆盖最近一次成功经营查询的追问上下文，也不生成查询图表或 SQL 导出。全局日期范围不代表每张表实际记录的最早、最晚日期。

未实现：任意 SQL 编辑、跨数据源接入、文件上传、自由因果归因、金额区间筛选、订单数量、任意逐笔财务流水、商机/PPL、项目风险、产品线回款分摊。已支持受控的客户合同清单、单笔应收计划排行、经营预测和应收分析。未知能力会明确提示，不静默替换查询。用户共享业务数据，个人会话、收藏和工作台设置等应用数据相互隔离。

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
- `backend/app/query/`：受控 SQL 编译、AST 校验、只读执行、数值计算及 SQL 展示。
- `backend/app/llm.py`：百炼兼容接口、模型结果校验及有限重试。
- `backend/app/retrieval.py`：业务目录生成、向量同步、精确词面匹配与 pgvector 召回。
- `backend/app/main.py`：应用工厂、中间件、异常处理与路由注册。
- `backend/app/api/`：按认证、会话、问数、工作台、反馈、语音和导出划分的 HTTP 接口。
- `backend/app/services/ask.py`：问数用例、执行状态与取消协调。
- `backend/app/repositories/`：应用数据访问、所有权过滤、事务与用户查询锁。
- `backend/app/contracts.py`：问数上下文、查询结果、执行记录和流事件契约。
- `backend/app/presentation/`：确定性摘要、分析步骤和 CSV 渲染。
- `backend/tests/unit/`、`backend/tests/integration/`：无需数据库的单元测试与显式启用的本地集成测试。
- `backend/app/schema.py`：27 张领域表结构；`alembic/`：冻结迁移。
- `backend/app/seed.py`：可重复、不可覆盖的模拟数据生成器。
- `frontend/src/pages/`：智能问数、应用配置和回复校对页面。
- `frontend/src/pages/Ask/components/`：Ask 专属的回答、图表、输入器和快捷问题组件。
- `frontend/src/layouts/WorkspaceLayout/`：布局外壳、Header、Menu 及共享 CSS Module。
- `frontend/src/models/`：共享接口契约；页面内部 `model/` 保存页面状态转换。
- `frontend/src/api/`：按认证、会话、工作台、问题、反馈和语音拆分的请求模块。
- `frontend/src/styles/`：基础全局 SCSS 和全局第三方覆盖；页面样式使用同目录的 CSS Modules。
- `frontend/vite.config.ts`：Vite 开发与打包配置；`frontend/build/` 存放前端 Dockerfile 与 Nginx 配置；`frontend/dist/` 是忽略提交的构建产物。
- `frontend/package.json`、`frontend/tsconfig.json`、`frontend/index.html`：保留在前端根目录的工具与应用入口。
- `scripts/`：环境准备、数据库运维和显式执行的模型评估脚本，详见 `scripts/README.md`。
- `docs/architecture.md`：执行边界与后续扩展。

模型仅接收召回的业务目录、合法实体值、用户问题和近期上下文，不获得数据库账号或 API Key。pgvector 只选择相关指标、维度、表字段、实体和示例；模型仍只生成受 Pydantic 约束的计划，SQL 由程序编译并经 SQLGlot 校验。第一版直接使用 SQLAlchemy + pgvector，不引入 LlamaIndex。
