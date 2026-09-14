# 后端以外的结构检查

检查日期：2026-09-14。范围包括前端源码、构建、Compose 接线、开发脚本和项目说明；未修改后端实现和数据库。

## 本轮已处理

- 前端 Dockerfile 和 Nginx 配置集中到 `frontend/build/`；Compose 同步修改路径。Vite 配置按后续约定放回 `frontend/vite.config.ts`，npm scripts 使用默认入口。
- 删除未被应用、脚本和文档使用的旧静态原型 `demo.html`，以及已被替代的 Workbench 空目录。
- 删除已跟踪的 `frontend/tsconfig.tsbuildinfo`；构建改用 `tsc --noEmit`，忽略后续增量缓存。
- 清除设置页未使用的 Alert 导入、注释 JSX 及对应失效样式。类型检查启用未使用变量、参数及副作用导入检查。
- Docker 构建上下文排除各层目录的本地环境文件、Vite 缓存和 TS 增量缓存，避免把前端本地环境文件复制进构建阶段。
- 修正旧开发脚本中的 Vite 启动入口和访问端口。保留数据库迁移、维护和模型评估脚本，并补充用途说明。
- 更新 README 中失效的组件路径、Less 样式描述、反馈功能说明及 Compose 端口说明。
- 从 `main.tsx` 递归追踪静态和动态相对导入，当前没有不可达的业务 TS/TSX 文件。声明文件和 SCSS 的 `@use` 不按业务 TS 入口判断。

## 可靠性问题处理结果

以下问题已在后续修复中处理。没有修改后端实现、引入生产依赖或添加测试框架。

| 优先级 | 位置 | 具体问题及建议 |
| --- | --- | --- |
| 高 | `frontend/src/pages/Ask/hooks/useVoiceRecorder.ts` | 已修复：卸载先解绑再停止录音，取消转写请求，停止晚到的授权媒体流；授权、停止回调及转写期间阻止重复启动。 |
| 高 | `frontend/src/pages/Ask/hooks/useSpeechPlayer.ts` | 已修复：卸载或文本变化取消合成；每个异步阶段检查有效性，释放播放器、事件与对象 URL，晚到响应不播放。 |
| 中 | `frontend/src/pages/Feedback/FeedbackPage.tsx` | 已修复：区分输入草稿与已提交查询，用单一 effect 加载，切换条件与分页取消旧请求；旧响应及 finally 不覆盖当前状态。 |
| 中 | `frontend/src/api/askStream.ts` | 已修复：独立解析与校验 status/analysis/result；区分指标与基础资料契约，保留旧指标计划兼容；消费异常原样传播，取消/异常均释放 reader，缺失结果明确报错。 |
| 中 | `frontend/src/layouts/WorkspaceLayout/WorkspaceLayout.module.scss` | 已修复：1050px 断点内补充折叠宽度 78px，避免展开宽度 210px 覆盖折叠态。 |
| 低 | `frontend/src/api/conversations.ts`、`frontend/src/models/ask.ts` | 已修复：失败状态限制为真实集合，删除展示层 success 断言；比较值与后端 previous_period 对齐，基础资料计划不再要求指标专属字段。 |
| 低 | `docs/architecture.md` | 已核对后端，更新反馈查看权限、超级管理员处理能力。旧开发/维护脚本用途明确，继续保留。 |

## 按需保留

- 用户明确暂不考虑 PC 首屏优化，因此保留业务路由同步导入，不新增路由懒加载。原有 ECharts 按需加载不变，体积警告不屏蔽。

## 规范与目录归属整理

- 接口类型跟随 API 领域：会话在 `api/conversations.ts`，配置和目录在 `api/workbench.ts`，问题和收藏在 `api/questions.ts`；`models/ask.ts` 仅保留复用的查询计划、结果和分析步骤。页面 reducer 状态仍在 Ask 的 `model/`，没有新增中转导出或重复类型别名。
- 删除 `config/workbench.ts` 及其空目录。设置页只有成功读取服务端配置后才展示编辑表单；失败时明确提示并允许重试，卸载时取消请求。移除硬编码的向量模型名称说明。
- 设置与反馈的共享内容样式迁至 `styles/management.module.scss`；Layout/Header/Menu 的样式仍归布局模块。目录抽屉标题样式局部化，唯一保留的全局 Ant Design 覆盖是表格等宽数字，并在规范中说明例外。
- 旧启动脚本改名为 `scripts/dev-legacy.sh`，明确提示旧数据库用途，固定前端代理到它启动的本机 8000 端口。未执行旧数据库启动、迁移或初始化，未修改后端代码。
- 新增前端 Prettier 配置、忽略列表及 `format` / `format:check`，统一现有前端格式；未安装依赖或测试框架。同步更新 AGENTS 与前端规范，默认页面目录不再包含 `api/`。

### 本次整理验证

- `npm run format:check`、TypeScript 检查、生产构建、Shell 语法与 Git 空白检查通过。主包及 ECharts 体积警告保持不变。
- 使用临时浏览器检查页挂载实际设置组件，在 StrictMode 下验证：接口失败后无编辑表单；接口恢复后重试成功；编辑弹窗显示返回值而非默认值。检查页已删除，没有向云端或本地后端提交配置。
- 使用真实本地后端与调整后的 API 函数检查配置、目录、收藏、常见问题、会话读取、6 条历史响应解析以及配置请求取消。未调用真实问数模型、运行模型评估或修改业务数据。
- 临时页面打开设置弹窗时观察到 Ant Design 5 对 React 19 的兼容提示；尚未进行全站交互兼容性回归。本轮不扩大到依赖升级。
- 正常开发服务仍使用原有云端代理配置，联调没有切换该服务的代理目标。

保留 `node_modules/`、`dist/`、运行数据、环境文件及历史评估报告。它们分别是依赖、当前构建输出、本地持久状态和可追溯记录，不是无用源文件。

## 验证结果

- TypeScript 检查和 Vite 生产构建通过；Compose 配置校验及前端 Docker 镜像构建通过，未重启现有服务。
- 新开发入口在 5881 启动，代理本地 Compose `/api/health` 返回 `ok`。浏览器 Ask 页面完成真实配置数据加载，控制台无错误或警告。
- Shell 语法与 Git 空白检查通过，所检查源码、构建、脚本和文档目录无空目录。
- 主包与 ECharts 大于 500 KB 的警告仍存在；Docker 使用的 npm 另提示两个依赖安装脚本的 allowScripts 配置尚未覆盖，但安装和构建成功。
- 后续修复已使用真实本地后端验证 20 条历史回答契约、反馈列表、无效会话 404、一次基础资料完整 NDJSON 问数以及流取消。仅创建并删除一个明确的联调会话，未删除或覆盖已有会话；未运行模型评估套件。
- 临时 Node 检查覆盖 UTF-8 跨字节分块、空行和尾行、无效 JSON/字段/事件、无最终结果、消费方异常、取消及 reader 解锁。检查脚本不加入项目，也未安装测试框架。
- 受控生命周期检查覆盖重复授权、授权晚到、卸载不转写、转写请求取消、合成/Blob 晚到、暂停继续及播放器/URL 释放。这不等同于真实麦克风和扬声器测试。
- 尚未完成登录后的浏览器交互回归、真实音频硬件/音频服务验证，以及反馈列表在网络延迟下的浏览器竞态复现。
