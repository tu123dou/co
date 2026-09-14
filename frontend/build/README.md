# 前端构建配置

- `../vite.config.ts`：开发服务、API 代理和打包配置，位于 `frontend/` 根目录，使用 Vite 默认发现机制。
- `Dockerfile`：前端多阶段镜像构建。Docker 构建上下文为仓库根目录，Compose 已配置对应路径。
- `nginx.conf`：静态资源、SPA 路由回退和 NDJSON API 代理。

在 `frontend/` 执行 `npm run dev`、`npm run typecheck`、`npm run build` 或 `npm run preview`。Vite 自动读取前端根目录的配置。预览只提供构建后的静态页面，不提供开发 API 代理；完整联调使用开发服务或 Compose。

构建输出在 `frontend/dist/`，不提交到 Git。TypeScript 只检查类型，不生成增量缓存。`package.json`、锁文件、`tsconfig.json` 和 `index.html` 继续留在 `frontend/`，便于包管理器、编辑器和容器构建使用。

代码格式由前端根目录 `.prettierrc.json` 统一定义；运行 `npm run format:check` 检查，`npm run format` 整理。`.prettierignore` 排除依赖、构建产物、锁文件和本地环境文件。
