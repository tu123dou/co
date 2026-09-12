"""SQLAlchemy 数据库结构定义。

analytics 模式保存用于经营分析的基础资料、合同和金额流水；app 模式保存用户、
对话、查询审计及向量索引。这里描述表、字段、主外键和约束，Alembic 再把这些结构
变更应用到 PostgreSQL。字段中文说明统一来自 catalog.py。
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Column as C,
)
from sqlalchemy import (
    ForeignKey as FK,
)
from sqlalchemy import (
    Integer as I,
)
from sqlalchemy import (
    Numeric as N,
)
from sqlalchemy import (
    String as S,
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .catalog import apply_catalog

metadata = MetaData()


def table(name, *columns, schema="analytics"):
    """默认在 analytics 业务模式中声明 SQLAlchemy 表。"""
    return Table(name, metadata, *columns, schema=schema)


def idcol():
    return C("id", I, primary_key=True)


def ref(name, target, **kw):
    return C(name, I, FK(target), nullable=False, **kw)


def money(name):
    return C(name, N(18, 2), nullable=False)


def created():
    return C(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# 基础资料表：组织、行业、客户、产品线、产品和销售人员。
# 这些表主要提供名称、分类和归属关系，供业务单据引用。
org_units = table(
    "org_units",
    idcol(),
    C("code", S(40), unique=True, nullable=False),
    C("name", S(80), unique=True, nullable=False),
    C("unit_type", S(30), nullable=False),
    C("region", S(30)),
    C("city", S(30)),
    C("parent_id", I, FK("analytics.org_units.id")),
)
industries = table("industries", idcol(), C("code", S(40), unique=True, nullable=False), C("name", S(50), unique=True, nullable=False))
customers = table(
    "customers",
    idcol(),
    C("code", S(50), unique=True, nullable=False),
    C("name", S(120), unique=True, nullable=False),
    C("province", S(30)),
    ref("industry_id", "analytics.industries.id"),
)
product_lines = table(
    "product_lines", idcol(), C("code", S(40), unique=True, nullable=False), C("name", S(60), unique=True, nullable=False)
)
products = table(
    "products",
    idcol(),
    C("code", S(50), unique=True, nullable=False),
    C("name", S(80), nullable=False),
    C("model", S(80), nullable=False),
    ref("product_line_id", "analytics.product_lines.id"),
)
salespeople = table(
    "salespeople",
    idcol(),
    C("code", S(40), unique=True, nullable=False),
    C("name", S(60), nullable=False),
    ref("org_unit_id", "analytics.org_units.id"),
)
# 合同主表保存一份合同的共同信息，合同明细表保存每种产品和对应金额。
# 一份合同可以有多条合同明细，这是一对多关系。
contracts = table(
    "contracts",
    idcol(),
    C("number", S(30), unique=True, nullable=False),
    C("name", S(160), nullable=False),
    ref("customer_id", "analytics.customers.id"),
    ref("org_unit_id", "analytics.org_units.id"),
    ref("salesperson_id", "analytics.salespeople.id"),
    C("signed_date", Date, nullable=False),
    C("status", S(20), nullable=False),
)
contract_items = table(
    "contract_items",
    idcol(),
    ref("contract_id", "analytics.contracts.id"),
    ref("product_id", "analytics.products.id"),
    C("quantity", N(12, 2), nullable=False),
    C("unit_name", S(20), nullable=False),
    C("tax_rate", N(6, 4), nullable=False),
    money("amount_ex_tax"),
    money("amount_with_tax"),
    CheckConstraint("quantity > 0"),
    CheckConstraint("tax_rate >= 0"),
    CheckConstraint("amount_ex_tax >= 0"),
)
# 经营事实表：收入、回款和成本分别记录，因为三者发生时间和统计口径不同。
revenue_entries = table(
    "revenue_entries",
    idcol(),
    ref("contract_item_id", "analytics.contract_items.id"),
    C("recognition_date", Date, nullable=False),
    money("amount_ex_tax"),
    CheckConstraint("amount_ex_tax >= 0"),
)
payment_entries = table(
    "payment_entries",
    idcol(),
    ref("contract_id", "analytics.contracts.id"),
    C("payment_date", Date, nullable=False),
    money("amount_ex_tax"),
    CheckConstraint("amount_ex_tax >= 0"),
)
cost_entries = table(
    "cost_entries",
    idcol(),
    ref("contract_item_id", "analytics.contract_items.id"),
    C("cost_date", Date, nullable=False),
    money("amount_ex_tax"),
    CheckConstraint("amount_ex_tax >= 0"),
)
# 月度目标以“月份+经营单元+产品线”为唯一粒度，不能下钻到客户或合同。
monthly_targets = table(
    "monthly_targets",
    idcol(),
    C("month", Date, nullable=False),
    ref("org_unit_id", "analytics.org_units.id"),
    ref("product_line_id", "analytics.product_lines.id"),
    money("revenue_target"),
    money("floor_amount"),
    money("forecast_amount"),
    UniqueConstraint("month", "org_unit_id", "product_line_id"),
    CheckConstraint("revenue_target > 0"),
    CheckConstraint("floor_amount >= 0"),
    CheckConstraint("forecast_amount >= 0"),
)
# 应收计划按合同记录应收、已核销金额和到期日，余额由两项金额相减得到。
receivable_entries = table(
    "receivable_entries",
    idcol(),
    ref("contract_id", "analytics.contracts.id"),
    C("due_date", Date, nullable=False),
    money("amount_ex_tax"),
    money("settled_amount_ex_tax"),
    C("status", S(20), nullable=False),
    CheckConstraint("amount_ex_tax >= 0"),
    CheckConstraint("settled_amount_ex_tax >= 0"),
    CheckConstraint("settled_amount_ex_tax <= amount_ex_tax"),
)
# 以下 app 模式表保存账号、对话、执行审计和语义检索数据。
users = table(
    "users",
    idcol(),
    C("username", S(80), nullable=False, unique=True),
    C("password_hash", Text, nullable=False),
    C("display_name", S(80), nullable=False),
    C("active", Boolean, nullable=False, server_default="true"),
    created(),
    schema="app",
)
conversations = table(
    "conversations",
    C("id", S(36), primary_key=True),
    ref("user_id", "app.users.id"),
    C("title", S(100), nullable=False),
    C("pinned", Boolean, nullable=False, server_default="false"),
    C("context", JSONB, nullable=False, server_default="{}"),
    created(),
    C("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    schema="app",
)
messages = table(
    "messages",
    C("id", S(36), primary_key=True),
    C(
        "conversation_id",
        S(36),
        FK("app.conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    C("role", S(20), nullable=False),
    C("content", Text, nullable=False),
    C("result", JSONB),
    created(),
    schema="app",
)
query_runs = table(
    "query_runs",
    C("id", S(36), primary_key=True),
    C("message_id", S(36), FK("app.messages.id", ondelete="CASCADE"), nullable=False),
    C("plan", JSONB),
    C("sql", Text),
    C("parameters", JSONB),
    C("status", S(30), nullable=False),
    C("error_code", S(50)),
    C("duration_ms", I),
    C("model", S(100)),
    C("usage", JSONB),
    C("dataset_version", S(80)),
    created(),
    schema="app",
)
favorite_questions = table(
    "favorite_questions",
    idcol(),
    ref("user_id", "app.users.id"),
    C("question", S(1000), nullable=False),
    created(),
    UniqueConstraint("user_id", "question"),
    schema="app",
)
user_workbench_settings = table(
    "user_workbench_settings",
    C(
        "user_id",
        I,
        FK("app.users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    C("welcome_enabled", Boolean, nullable=False, server_default="true"),
    C("welcome_title", S(100), nullable=False),
    C("welcome_message", S(500), nullable=False),
    C("starter_questions", JSONB, nullable=False, server_default="[]"),
    C("suggestions_enabled", Boolean, nullable=False, server_default="true"),
    C("common_questions_enabled", Boolean, nullable=False, server_default="true"),
    C("common_question_threshold", I, nullable=False, server_default="3"),
    C("llm_model", S(100), nullable=False),
    C("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint(
        "common_question_threshold BETWEEN 1 AND 100",
        name="ck_user_workbench_settings_common_threshold",
    ),
    schema="app",
)
user_question_stats = table(
    "user_question_stats",
    idcol(),
    C("user_id", I, FK("app.users.id", ondelete="CASCADE"), nullable=False),
    C("normalized_question", S(1000), nullable=False),
    C("question", S(1000), nullable=False),
    C("success_count", I, nullable=False, server_default="1"),
    C("last_asked_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("user_id", "normalized_question"),
    CheckConstraint("success_count > 0", name="ck_user_question_stats_success_count"),
    schema="app",
)
feedbacks = table(
    "feedbacks",
    idcol(),
    ref("user_id", "app.users.id"),
    C("message_id", S(36), FK("app.messages.id", ondelete="CASCADE"), nullable=False),
    C("comment", Text, nullable=False),
    C("status", S(20), nullable=False, server_default="pending"),
    C("resolution_note", Text),
    created(),
    C("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("status IN ('pending', 'resolved')", name="ck_feedbacks_status"),
    schema="app",
)
metric_definitions = table(
    "metric_definitions",
    idcol(),
    C("code", S(80), nullable=False),
    C("name", S(80), nullable=False),
    C("version", I, nullable=False),
    C("definition", JSONB, nullable=False),
    UniqueConstraint("code", "version"),
    schema="app",
)
dataset_versions = table(
    "dataset_versions",
    idcol(),
    C("version", S(80), unique=True, nullable=False),
    C("seed", I, nullable=False),
    C("start_date", Date, nullable=False),
    C("cutoff_date", Date, nullable=False),
    C("counts", JSONB, nullable=False),
    created(),
    schema="app",
)
semantic_documents = table(
    "semantic_documents",
    idcol(),
    C("document_key", S(240), nullable=False),
    C("kind", S(40), nullable=False),
    C("title", S(300), nullable=False),
    C("content", Text, nullable=False),
    C("metadata", JSONB, nullable=False, server_default="{}"),
    C("version", S(80), nullable=False),
    C("content_hash", S(64), nullable=False),
    C("active", Boolean, nullable=False, server_default="true"),
    created(),
    UniqueConstraint("document_key", "version"),
    schema="app",
)
# 文档与向量分表，便于同一文档支持多个分块或向量模型版本。
semantic_chunks = table(
    "semantic_chunks",
    idcol(),
    C(
        "document_id",
        I,
        FK("app.semantic_documents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    C("chunk_index", I, nullable=False, server_default="0"),
    C("content", Text, nullable=False),
    C("embedding", Vector(1024), nullable=False),
    C("embedding_model", S(100), nullable=False),
    created(),
    UniqueConstraint("document_id", "chunk_index", "embedding_model"),
    schema="app",
)
embedding_jobs = table(
    "embedding_jobs",
    C("id", S(36), primary_key=True),
    C("version", S(80), nullable=False),
    C("embedding_model", S(100), nullable=False),
    C("status", S(30), nullable=False),
    C("document_count", I, nullable=False, server_default="0"),
    C("error", Text),
    created(),
    C("finished_at", DateTime(timezone=True)),
    schema="app",
)
retrieval_events = table(
    "retrieval_events",
    C("id", S(36), primary_key=True),
    C("query_run_id", S(36), FK("app.query_runs.id", ondelete="CASCADE")),
    C("question", Text, nullable=False),
    C("embedding_model", S(100), nullable=False),
    C("top_k", I, nullable=False),
    C("duration_ms", I, nullable=False),
    C("hits", JSONB, nullable=False),
    created(),
    schema="app",
)
for t, cols in [
    (contracts, ["signed_date"]),
    (contracts, ["customer_id"]),
    (contract_items, ["contract_id"]),
    (revenue_entries, ["recognition_date", "contract_item_id"]),
    (payment_entries, ["payment_date", "contract_id"]),
    (cost_entries, ["cost_date", "contract_item_id"]),
    (receivable_entries, ["due_date", "contract_id"]),
    (messages, ["conversation_id", "created_at"]),
    (conversations, ["user_id", "updated_at"]),
    (user_question_stats, ["user_id", "success_count", "last_asked_at"]),
    (semantic_documents, ["kind", "active"]),
    (semantic_chunks, ["embedding_model"]),
    (embedding_jobs, ["status", "created_at"]),
    (retrieval_events, ["query_run_id", "created_at"]),
]:
    Index("ix_" + t.name + "_" + "_".join(cols), *[t.c[x] for x in cols])

apply_catalog(metadata)
