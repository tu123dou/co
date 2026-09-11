"""Twenty domain tables, split into app and analytics schemas."""

from sqlalchemy import (
    MetaData,
    Table,
    Column as C,
    Integer as I,
    String as S,
    Text,
    Numeric as N,
    Date,
    DateTime,
    Boolean,
    ForeignKey as FK,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()


def table(name, *columns, schema="analytics"):
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


org_units = table(
    "org_units",
    idcol(),
    C("name", S(80), unique=True, nullable=False),
    C("region", S(30), nullable=False),
    C("city", S(30), nullable=False),
    C("parent_id", I, FK("analytics.org_units.id")),
)
industries = table("industries", idcol(), C("name", S(50), unique=True, nullable=False))
customers = table(
    "customers",
    idcol(),
    C("name", S(120), unique=True, nullable=False),
    ref("industry_id", "analytics.industries.id"),
)
product_lines = table(
    "product_lines", idcol(), C("name", S(60), unique=True, nullable=False)
)
products = table(
    "products",
    idcol(),
    C("name", S(80), nullable=False),
    ref("product_line_id", "analytics.product_lines.id"),
)
salespeople = table(
    "salespeople",
    idcol(),
    C("name", S(60), nullable=False),
    ref("org_unit_id", "analytics.org_units.id"),
)
contracts = table(
    "contracts",
    idcol(),
    C("number", S(30), unique=True, nullable=False),
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
    money("amount_ex_tax"),
    CheckConstraint("amount_ex_tax >= 0"),
)
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
monthly_targets = table(
    "monthly_targets",
    idcol(),
    C("month", Date, nullable=False),
    ref("org_unit_id", "analytics.org_units.id"),
    ref("product_line_id", "analytics.product_lines.id"),
    money("revenue_target"),
    UniqueConstraint("month", "org_unit_id", "product_line_id"),
    CheckConstraint("revenue_target > 0"),
)
users = table(
    "users",
    idcol(),
    C("username", S(80), nullable=False, unique=True),
    C("password_hash", Text, nullable=False),
    C("display_name", S(80), nullable=False),
    C("role", S(20), nullable=False),
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
feedbacks = table(
    "feedbacks",
    idcol(),
    ref("user_id", "app.users.id"),
    C("message_id", S(36), FK("app.messages.id", ondelete="CASCADE"), nullable=False),
    C("comment", Text, nullable=False),
    C("status", S(20), nullable=False, server_default="pending"),
    created(),
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
for t, cols in [
    (contracts, ["signed_date"]),
    (contracts, ["customer_id"]),
    (contract_items, ["contract_id"]),
    (revenue_entries, ["recognition_date", "contract_item_id"]),
    (payment_entries, ["payment_date", "contract_id"]),
    (cost_entries, ["cost_date", "contract_item_id"]),
    (messages, ["conversation_id", "created_at"]),
    (conversations, ["user_id", "updated_at"]),
]:
    Index("ix_" + t.name + "_" + "_".join(cols), *[t.c[x] for x in cols])
