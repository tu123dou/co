# 架构与实施边界

## 请求路径

浏览器 → 同源 API → 登录身份和会话归属校验 → 百炼自然语言解析 → Pydantic 查询计划校验 → 业务实体值校验 → 程序 SQL 编译 → SQLGlot AST 校验 → PostgreSQL 只读事务 → Decimal 指标计算 → 确定性文字、图表和取数依据。

执行进度通过 NDJSON 流返回；这是真实阶段状态，不展示或伪造模型内部思维链。每次回答保存数据版本、模型、用量、参数、SQL及耗时。暂不提供任意模型 SQL 执行。

## 数据粒度

contract_items 是产品粒度的签约事实；revenue_entries/cost_entries 引用该明细。payment_entries 只引用合同。monthly_targets 的唯一粒度为 月×经营单元×产品线。不同事实分支使用 UNION ALL 再聚合，避免多对多连接导致重复累计。

八个应用表为 users、conversations、messages、query_runs、favorite_questions、feedbacks、metric_definitions、dataset_versions。指标的可执行语义由版本管理中的 semantic.py 控制；metric_definitions 保存部署版本的业务说明。变更公式时需同时升级指标版本和历史口径展示，不能直接用新公式重写历史回答。

## 执行控制

- 应用账号 app 为 schema 所有者，负责迁移及应用写入。查询账号 analyst 只有 analytics 的 USAGE/SELECT。
- SQLGlot 接受单条 SELECT，扫描整棵 AST，限制语句类型、表、schema及函数。真正的 SQL 只来自程序编译器，筛选值以绑定参数传入。
- 数据库每次开启 READ ONLY 事务，设置10秒 statement_timeout。分组最多500组，用户展示limit最多100。
- 每个用户同一时刻只允许一个问数请求，通过 PostgreSQL advisory lock 在多后端进程间协调。
- 中止浏览器请求会取消模型调用；已经在数据库执行的查询可能继续到完成或超时，响应生成停止后仍释放会话锁。
- HTTP-only、SameSite=Strict cookie 认证；修改请求校验 Origin。JWT 有效期12小时。角色包括admin/user。
- 当前登录限流为进程内基础限流，适合单机第一版；多实例生产环境应在入口增加共享限流和完整审计。
- 模型返回原始上游错误及密钥不向浏览器透传。连接/超时/限流失败最多尝试3次；无效结构最多请求模型修正一次。

## 扩展方向

1. 接入真实数据库：保留同一查询计划，在数据适配层注册业务字段、维度和合法关联，不开放应用schema。
2. 扩充指标：声明粒度、公式、允许维度和测试基准；版本化迁移，不凭同名字段自动关联。
3. 表和说明文档增多后：增加 pgvector 召回或 LlamaIndex 检索，只负责选择上下文，不越过执行校验。
4. 组织数据权限：在解析之前提供用户可见目录，并在编译器或数据库RLS中强制过滤。不能只依靠prompt限制。
5. 公开生产环境：HTTPS、备份恢复演练、共享限流、密码修改与账号管理、独立迁移任务、监控告警及并发压测。

## 已知限制

复杂筛选、明细查询、跨指标自由运算及因果推断不在第一版查询计划中。反馈目前保存与提交，无管理员处理页面。结果摘要为程序生成，模型仅负责理解自然语言。演示数据不包含税额、应收核销和完整会计科目，不作为财务账套。
