---
name: deploy-ai-wenshu
description: Deploy the AI Wenshu/Jingguan project to its configured Alibaba Cloud ECS server. Use when the user asks to deploy, publish, update, or restart this project's remote frontend and backend; do not use for local-only Docker work or unrelated servers.
---

# 部署 AI 问数服务器

把当前项目已经推送到 `origin/feature/co` 的版本部署到固定的阿里云 ECS 实例。

## 固定目标

- Workbench 实例：`i-2vcgdfqug0vm5icpp2nm`
- 交互登录：`workbench connect -i i-2vcgdfqug0vm5icpp2nm`
- 服务器项目目录：`/opt/ai-wenshu/co`
- 部署分支：`feature/co`
- Compose 文件：`/opt/ai-wenshu/co/compose.yaml`
- 公网入口：`http://8.137.78.125`
- 服务器健康接口：`http://127.0.0.1/api/health`

用户明确要求部署、发布或更新远程服务器时，视为允许执行本 Skill 的远程更新流程。工具本身要求授权时，仍应按工具规则申请授权。

## 部署流程

日常部署优先使用可逐步审计的 `workbench exec`；`workbench connect` 只作为需要交互排障时的登录入口。每次 `workbench exec` 都是独立 shell，不依赖前一次调用的 `cd` 或环境变量。使用 `git -C`，以及 Docker Compose 的 `--project-directory` 和 `-f` 参数传递绝对路径。

### 1. 部署前检查

先检查服务器 Git 状态：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "git -C /opt/ai-wenshu/co status --short --branch"
```

只检查环境文件是否存在，不读取其内容：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "test -f /opt/ai-wenshu/co/.env"
```

只在以下条件都满足时继续：

- 当前分支是 `feature/co`。
- 服务器工作树没有未提交或未跟踪文件。
- `/opt/ai-wenshu/co/.env` 已存在；只检查存在性，禁止读取或输出内容。

如果分支不符或工作树不干净，停止部署并向用户报告。不要自动 `checkout`、`reset`、`stash`、删除或覆盖服务器文件。

### 2. 拉取部署分支

使用快进模式拉取，禁止在服务器生成合并提交：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 120 --command "git -C /opt/ai-wenshu/co pull --ff-only origin feature/co"
```

如果出现非快进、认证或网络错误，停止并报告错误，不使用强制拉取。

### 3. 构建并启动前后端

重建前端和后端镜像并启动 Compose 服务：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 600 --command "docker compose --project-directory /opt/ai-wenshu/co -f /opt/ai-wenshu/co/compose.yaml up --build -d"
```

该命令会等待数据库健康，后端启动时自动执行 Alembic 迁移、只读账号授权和安全的数据初始化，再启动 FastAPI；前端在后端健康后启动 Nginx。

不得执行 `docker compose down -v`、删除 `postgres_data_v2`、重建数据库数据目录或修改服务器 `.env`。不要因为普通部署自动运行语义索引同步；只有业务目录、指标、维度、标准实体发生变化或用户明确要求时才运行。

### 4. 验证部署

依次检查：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "git -C /opt/ai-wenshu/co rev-parse --short HEAD"
```

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "docker compose --project-directory /opt/ai-wenshu/co -f /opt/ai-wenshu/co/compose.yaml ps"
```

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "curl --fail --silent http://127.0.0.1/api/health"
```

```sh
curl --fail --silent --show-error --head --max-time 15 http://8.137.78.125/
```

成功标准：

- 数据库和后端显示 healthy。
- 前端容器处于 Up 状态并监听宿主机 80 端口。
- 健康接口返回 `{"status":"ok"}`。
- 公网入口返回 HTTP 200。

如果容器未健康，读取必要的最近日志定位问题：

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "docker compose --project-directory /opt/ai-wenshu/co -f /opt/ai-wenshu/co/compose.yaml logs --tail=100 backend"
```

```sh
workbench exec -i i-2vcgdfqug0vm5icpp2nm --timeout 60 --command "docker compose --project-directory /opt/ai-wenshu/co -f /opt/ai-wenshu/co/compose.yaml logs --tail=100 frontend"
```

不要输出 Cookie、Token、API Key、数据库密码或 `.env` 内容。只对明确的瞬态网络错误重试一次；构建、迁移或程序错误应先报告根因，不进行破坏性恢复。

## 结果反馈

部署结束后向用户明确说明：

- 拉取到的分支和最终提交号。
- 前端、后端和数据库容器状态。
- 内部健康接口和公网入口检查结果。
- 是否执行了数据库迁移或语义索引同步。
- 构建警告、失败步骤或仍未验证的路径。

不要仅以构建成功判断部署成功，必须完成容器状态和 HTTP 检查。
