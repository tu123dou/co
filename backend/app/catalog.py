"""数据库业务字典。

TABLE_CATALOG 为每张表维护业务用途、单行代表什么以及每个字段的含义。这些说明
会写入 PostgreSQL COMMENT，所以可以直接在 DBeaver 中查看。schema.py 加载时还会
核对目录与实际模型，新增表或字段却忘记写说明时，应用会立即报错。
"""

TABLE_CATALOG = {
    "analytics.org_units": {
        "comment": "经营单元维表。用途：维护销售经营组织、所属区域和城市层级。粒度：每行一个经营单元。",
        "columns": {
            "id": "经营单元内部唯一标识。",
            "code": "经营单元稳定业务编码；全表唯一。",
            "name": "经营单元名称，例如北京代表处；全表唯一。",
            "unit_type": "组织类型，例如代表处、办事处或系统部。",
            "region": "经营大区名称，例如华北、华东。",
            "city": "经营单元所在城市名称。",
            "parent_id": "上级经营单元标识，关联本表 id；顶级经营单元为空。",
        },
    },
    "analytics.industries": {
        "comment": "客户行业维表。用途：维护客户所属的标准行业分类。粒度：每行一个行业分类。",
        "columns": {"id": "行业内部唯一标识。", "code": "行业稳定业务编码；全表唯一。", "name": "行业名称；全表唯一。"},
    },
    "analytics.customers": {
        "comment": "客户维表。用途：维护合同客户及其标准行业归属。粒度：每行一个客户主体。",
        "columns": {
            "id": "客户内部唯一标识。",
            "code": "客户稳定业务编码；全表唯一。",
            "name": "客户主体名称；当前数据中全表唯一。",
            "province": "客户主要项目所在地省级行政区。",
            "industry_id": "客户所属行业标识，关联 industries.id。",
        },
    },
    "analytics.product_lines": {
        "comment": "产品线维表。用途：维护产品的一级业务分类。粒度：每行一个产品线。",
        "columns": {"id": "产品线内部唯一标识。", "code": "产品线稳定业务编码；全表唯一。", "name": "产品线名称；全表唯一。"},
    },
    "analytics.products": {
        "comment": "产品维表。用途：维护可签约产品及其产品线归属。粒度：每行一个产品。",
        "columns": {
            "id": "产品内部唯一标识。",
            "code": "产品稳定业务编码；全表唯一。",
            "name": "产品名称。",
            "model": "产品型号，用于细分产品分析。",
            "product_line_id": "所属产品线标识，关联 product_lines.id。",
        },
    },
    "analytics.salespeople": {
        "comment": "销售人员维表。用途：维护销售人员及其经营单元归属。粒度：每行一个销售人员。",
        "columns": {
            "id": "销售人员内部唯一标识。",
            "code": "销售人员稳定业务编码；全表唯一。",
            "name": "销售人员姓名或展示名称。",
            "org_unit_id": "所属经营单元标识，关联 org_units.id。",
        },
    },
    "analytics.contracts": {
        "comment": "销售合同主表。用途：记录合同主体、签约组织、负责人、签约日期和状态。粒度：每行一份销售合同，不含产品拆分金额。",
        "columns": {
            "id": "合同内部唯一标识。",
            "number": "合同编号；全表唯一。",
            "name": "合同名称。",
            "customer_id": "合同客户标识，关联 customers.id。",
            "org_unit_id": "合同归属经营单元标识，关联 org_units.id。",
            "salesperson_id": "合同负责人标识，关联 salespeople.id。",
            "signed_date": "合同签约日期；签约额按此字段归属统计期间。",
            "status": "合同状态；active 表示有效，cancelled 表示取消。取消合同不计入经营指标。",
        },
    },
    "analytics.contract_items": {
        "comment": "合同产品明细事实表。用途：记录合同中各产品的签约金额，是签约额指标的基础事实。粒度：每行一份合同中的一个产品明细。",
        "columns": {
            "id": "合同产品明细内部唯一标识。",
            "contract_id": "所属合同标识，关联 contracts.id。",
            "product_id": "签约产品标识，关联 products.id。",
            "quantity": "签约产品数量，必须大于0。", "unit_name": "计量单位，例如台或套。", "tax_rate": "合同明细税率。",
            "amount_ex_tax": "该合同产品明细的不含税签约金额，单位：元，必须大于或等于0。",
            "amount_with_tax": "该合同产品明细的含税签约金额，单位：元。",
        },
    },
    "analytics.revenue_entries": {
        "comment": "收入确认事实表。用途：记录合同产品明细分期确认的收入，是确认收入指标的基础事实。粒度：每行一次合同产品明细在某日的收入确认。",
        "columns": {
            "id": "收入确认记录内部唯一标识。",
            "contract_item_id": "对应合同产品明细标识，关联 contract_items.id。",
            "recognition_date": "收入确认日期；确认收入按此字段归属统计期间。",
            "amount_ex_tax": "本次确认的不含税收入金额，单位：元，必须大于或等于0。",
        },
    },
    "analytics.payment_entries": {
        "comment": "合同回款事实表。用途：记录合同级回款，是回款额指标的基础事实。粒度：每行一份合同在某日的一次回款；未拆分到产品明细。",
        "columns": {
            "id": "回款记录内部唯一标识。",
            "contract_id": "对应合同标识，关联 contracts.id。",
            "payment_date": "实际回款日期；回款额按此字段归属统计期间。",
            "amount_ex_tax": "本次回款的管理口径不含税折算金额，单位：元，必须大于或等于0。",
        },
    },
    "analytics.cost_entries": {
        "comment": "直接成本确认事实表。用途：记录与合同产品收入确认相匹配的直接成本，是直接成本和毛利指标的基础事实。粒度：每行一次合同产品明细在某日的直接成本确认。",
        "columns": {
            "id": "直接成本记录内部唯一标识。",
            "contract_item_id": "对应合同产品明细标识，关联 contract_items.id。",
            "cost_date": "直接成本确认日期；直接成本按此字段归属统计期间。",
            "amount_ex_tax": "本次确认的直接成本金额，单位：元，必须大于或等于0。",
        },
    },
    "analytics.monthly_targets": {
        "comment": "月度收入目标事实表。用途：维护经营单元和产品线的月度确认收入目标。粒度：每行一个自然月、一个经营单元、一个产品线的目标，三者组合唯一。",
        "columns": {
            "id": "月度目标记录内部唯一标识。",
            "month": "目标月份，使用该月第一天表示；目标达成率仅按完整月份计算。",
            "org_unit_id": "目标所属经营单元标识，关联 org_units.id。",
            "product_line_id": "目标所属产品线标识，关联 product_lines.id。",
            "revenue_target": "当月不含税确认收入目标，单位：元，必须大于0。",
            "floor_amount": "当月保底收入预测，单位：元。", "forecast_amount": "当月滚动预测收入，单位：元。",
        },
    },
    "analytics.receivable_entries": {
        "comment": "合同应收计划事实表。用途：维护合同分期应收、结清状态和逾期账龄。粒度：每行一份合同的一期应收计划。",
        "columns": {"id": "应收计划内部唯一标识。", "contract_id": "对应合同标识。", "due_date": "该期应收到期日期。", "amount_ex_tax": "该期管理口径不含税应收金额，单位：元。", "settled_amount_ex_tax": "该期已核销金额，单位：元。", "status": "应收状态，例如待收、部分核销、已结清或逾期。"},
    },
    "app.users": {
        "comment": "应用用户表。用途：保存本地登录账号和展示信息。粒度：每行一个应用用户账号。该表不开放给问数查询账号。",
        "columns": {
            "id": "应用用户内部唯一标识。",
            "username": "登录用户名；全表唯一。",
            "password_hash": "使用随机盐和 scrypt 生成的密码哈希；不保存明文密码。",
            "display_name": "用户在工作台中的展示名称。",
            "active": "账号是否有效；false 时禁止登录。",
            "created_at": "账号创建时间，包含时区。",
        },
    },
    "app.conversations": {
        "comment": "智能问数会话表。用途：保存用户的会话标题、置顶状态和最近成功查询上下文。粒度：每行一个用户会话。",
        "columns": {
            "id": "会话唯一标识，使用 UUID 字符串。",
            "user_id": "会话所属用户标识，关联 users.id。",
            "title": "会话标题，首次提问时自动生成，可由用户重命名。",
            "pinned": "会话是否置顶显示。",
            "context": "最近一次成功查询的结构化计划 JSON，用于连续追问继承条件。",
            "created_at": "会话创建时间，包含时区。",
            "updated_at": "会话最后更新时间，包含时区，用于历史会话排序。",
        },
    },
    "app.messages": {
        "comment": "会话消息表。用途：保存用户问题、助手回答及可视化查询结果。粒度：每行一条会话消息。",
        "columns": {
            "id": "消息唯一标识，使用 UUID 字符串。",
            "conversation_id": "所属会话标识，关联 conversations.id；删除会话时级联删除。",
            "role": "消息角色；user 表示用户，assistant 表示问数助手。",
            "content": "用户问题或助手的文字回答。",
            "result": "助手消息的结构化结果 JSON，包含状态、指标、分组数据、图表和追溯信息；用户消息通常为空。",
            "created_at": "消息创建时间，包含时区。",
        },
    },
    "app.query_runs": {
        "comment": "问数执行记录表。用途：审计每次助手回答对应的查询计划、SQL、参数、模型和执行状态。粒度：每行一次问数执行。",
        "columns": {
            "id": "问数执行唯一标识，使用 UUID 字符串。",
            "message_id": "本次执行生成的助手消息标识，关联 messages.id；删除消息时级联删除。",
            "plan": "经模型解析并通过业务校验的结构化查询计划 JSON。",
            "sql": "程序根据查询计划编译并实际执行的参数化只读 SQL；多次对比查询以空行分隔。",
            "parameters": "各次 SQL 执行的绑定参数和追溯信息 JSON，不包含模型 API Key。",
            "status": "执行状态，例如 success、error、clarify、unsupported、cancelled。",
            "error_code": "标准化错误代码；成功时为空。",
            "duration_ms": "从接收问题到完成或失败的总耗时，单位：毫秒。",
            "model": "解析自然语言时使用的模型调用 ID。",
            "usage": "模型服务返回的 token 用量 JSON；服务未提供时为空对象。",
            "dataset_version": "执行时使用的数据集版本号，用于结果追溯。",
            "created_at": "执行记录创建时间，包含时区。",
        },
    },
    "app.favorite_questions": {
        "comment": "收藏问题表。用途：保存用户收藏的常用自然语言问题。粒度：每行一个用户收藏的问题；同一用户的问题文本唯一。",
        "columns": {
            "id": "收藏记录内部唯一标识。",
            "user_id": "收藏所属用户标识，关联 users.id。",
            "question": "用户收藏的自然语言问题原文。",
            "created_at": "收藏创建时间，包含时区。",
        },
    },
    "app.user_workbench_settings": {
        "comment": "用户工作台设置表。用途：保存每名用户独立的开场内容、快捷提问、延伸建议和主模型配置。粒度：每名用户一行。",
        "columns": {
            "user_id": "设置所属用户标识，同时作为主键；删除用户时级联删除。",
            "welcome_enabled": "是否在空白新对话中显示用户配置的开场内容。",
            "welcome_title": "新对话开场标题。",
            "welcome_message": "新对话开场说明文案。",
            "starter_questions": "有序的开场问题 JSON 数组，最多保存十条。",
            "suggestions_enabled": "是否在成功回答后显示下一步问题建议。",
            "common_questions_enabled": "是否在快捷提问中显示当前用户的常见问题。",
            "common_question_threshold": "同一问题成功查询多少次后成为常见问题。",
            "llm_model": "当前用户选择的主大模型调用 ID。",
            "updated_at": "设置最后更新时间，包含时区。",
        },
    },
    "app.user_question_stats": {
        "comment": "用户问题频次表。用途：按用户统计成功问数的常见问题候选。粒度：每名用户的每个标准化问题一行。",
        "columns": {
            "id": "问题统计记录内部唯一标识。",
            "user_id": "统计所属用户标识；删除用户时级联删除。",
            "normalized_question": "用于归并重复提问的标准化问题文本。",
            "question": "最近一次成功查询的问题原文，用于前端展示。",
            "success_count": "该问题成功完成问数的累计次数。",
            "last_asked_at": "最近一次成功查询时间，包含时区。",
        },
    },
    "app.feedbacks": {
        "comment": "回答反馈表。用途：保存用户针对某条助手回答提交的数据或口径问题。粒度：每行一次用户反馈。",
        "columns": {
            "id": "反馈记录内部唯一标识。",
            "user_id": "反馈提交用户标识，关联 users.id。",
            "message_id": "反馈对应的助手消息标识，关联 messages.id；删除消息时级联删除。",
            "comment": "用户填写的反馈内容。",
            "status": "反馈处理状态；pending 表示待处理，resolved 表示已处理。",
            "resolution_note": "回复校对时填写的处理说明或核查结论。",
            "created_at": "反馈提交时间，包含时区。",
            "updated_at": "反馈最后处理时间，包含时区。",
        },
    },
    "app.metric_definitions": {
        "comment": "指标定义版本表。用途：保存部署时的指标中文名称、口径、单位和适用维度快照。粒度：每行一个指标的一个版本，指标代码与版本组合唯一。",
        "columns": {
            "id": "指标定义记录内部唯一标识。",
            "code": "稳定的指标英文代码，例如 revenue。",
            "name": "指标中文名称，例如确认收入。",
            "version": "指标口径版本号；同一指标从1开始递增。",
            "definition": "指标口径、单位、基础事实及允许维度的 JSON 定义。",
        },
    },
    "app.dataset_versions": {
        "comment": "数据集版本表。用途：记录业务数据的生成版本、随机种子、覆盖时间和各表记录数。粒度：每行一个可追溯的数据集版本。",
        "columns": {
            "id": "数据集版本记录内部唯一标识。",
            "version": "数据集版本号；全表唯一。",
            "seed": "生成业务数据使用的固定随机种子。",
            "start_date": "该版本业务数据覆盖的最早日期。",
            "cutoff_date": "该版本业务数据截止日期；相对时间以此日期为参考。",
            "counts": "该版本各业务表及主要维表的记录数 JSON。",
            "created_at": "数据集版本登记时间，包含时区。",
        },
    },
    "app.semantic_documents": {
        "comment": "语义文档表。用途：保存指标、维度、数据库对象、业务实体和示例问法的可检索说明。粒度：每行一个语义对象的一个版本。",
        "columns": {
            "id": "语义文档内部唯一标识。",
            "document_key": "语义对象稳定键，同一版本内唯一。",
            "kind": "文档类型，例如 metric、dimension、table、entity 或 example。",
            "title": "供精确词面匹配和展示的文档标题。",
            "content": "发送给向量模型并在召回后提供给查询规划器的业务语义文本。",
            "metadata": "维度代码、实体值和来源对象等结构化元数据。",
            "version": "目录或数据集版本，用于隔离失效向量。",
            "content_hash": "文档内容 SHA-256，用于增量更新和幂等同步。",
            "active": "该文档当前是否可参与检索。",
            "created_at": "语义文档首次写入时间，包含时区。",
        },
    },
    "app.semantic_chunks": {
        "comment": "语义向量分块表。用途：保存语义文档分块及其 pgvector 向量。粒度：每行一个文档分块在一个向量模型下的表示。",
        "columns": {
            "id": "语义分块内部唯一标识。",
            "document_id": "所属语义文档标识；删除文档时级联删除。",
            "chunk_index": "分块在文档内的零基序号；当前短文档通常为0。",
            "content": "实际生成向量的分块文本。",
            "embedding": "1024维语义向量，仅用于候选上下文召回。",
            "embedding_model": "生成该向量的模型名称。",
            "created_at": "语义向量写入时间，包含时区。",
        },
    },
    "app.embedding_jobs": {
        "comment": "向量同步任务表。用途：记录每次语义目录嵌入任务的版本、状态和文档数量。粒度：每行一次同步任务。",
        "columns": {
            "id": "同步任务唯一标识，使用 UUID 字符串。",
            "version": "本次同步的目录或数据集版本。",
            "embedding_model": "本次使用的向量模型名称。",
            "status": "任务状态，例如 running、success 或 error。",
            "document_count": "本次成功处理的语义文档数量。",
            "error": "任务失败时的脱敏错误说明；成功时为空。",
            "created_at": "任务开始时间，包含时区。",
            "finished_at": "任务结束时间，包含时区；执行中为空。",
        },
    },
    "app.retrieval_events": {
        "comment": "语义召回审计表。用途：追踪一次问数使用的召回结果、耗时和向量模型。粒度：每行一次用户问题的语义召回。",
        "columns": {
            "id": "召回事件唯一标识，使用 UUID 字符串。",
            "query_run_id": "关联的问数执行标识；问数记录删除时级联删除。",
            "question": "用于召回的用户问题原文。",
            "embedding_model": "问题向量使用的模型名称。",
            "top_k": "本次配置的最大召回条数。",
            "duration_ms": "召回总耗时，单位：毫秒。",
            "hits": "召回文档键、类型、标题、距离和匹配方式的 JSON 数组。",
            "created_at": "召回事件写入时间，包含时区。",
        },
    },
}


def apply_catalog(metadata):
    """把中文目录附加到模型；表或字段缺少说明时立即报错。"""
    actual = set(metadata.tables)
    expected = set(TABLE_CATALOG)
    if actual != expected:
        raise RuntimeError(
            f"数据库目录与模型不一致，缺少目录={sorted(actual - expected)}，多余目录={sorted(expected - actual)}"
        )
    for key, spec in TABLE_CATALOG.items():
        table = metadata.tables[key]
        table.comment = spec["comment"]
        actual_columns = set(table.c.keys())
        expected_columns = set(spec["columns"])
        if actual_columns != expected_columns:
            raise RuntimeError(
                f"{key} 列目录不完整，缺少={sorted(actual_columns - expected_columns)}，多余={sorted(expected_columns - actual_columns)}"
            )
        for name, comment in spec["columns"].items():
            table.c[name].comment = comment
