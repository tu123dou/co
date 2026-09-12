"""语义检索迁移：创建 pgvector 文档、向量、同步任务和召回审计表。

Revision ID: 0003
Revises: 0002
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.catalog import TABLE_CATALOG

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _comment(table_name: str) -> None:
    spec = TABLE_CATALOG[f"app.{table_name}"]
    op.execute(
        "COMMENT ON TABLE app."
        + table_name
        + " IS '"
        + spec["comment"].replace("'", "''")
        + "'"
    )
    for name, comment in spec["columns"].items():
        op.execute(
            f"COMMENT ON COLUMN app.{table_name}.{name} IS '"
            + comment.replace("'", "''")
            + "'"
        )


def upgrade():
    """启用 vector 扩展并建立语义检索相关数据库对象。"""
    # The container init script installs the extension as the postgres owner.
    # Keeping this check here prevents silently deploying against plain Postgres.
    present = op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
    )
    if not present:
        raise RuntimeError("pgvector extension is required; initialize with the project compose stack")

    op.create_table(
        "semantic_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_key", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_key", "version"),
        schema="app",
    )
    op.create_table(
        "semantic_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("app.semantic_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", "embedding_model"),
        schema="app",
    )
    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        schema="app",
    )
    op.create_table(
        "retrieval_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_run_id", sa.String(36), sa.ForeignKey("app.query_runs.id", ondelete="CASCADE")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("hits", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_semantic_documents_kind_active", "semantic_documents", ["kind", "active"], schema="app")
    op.create_index("ix_semantic_chunks_embedding_model", "semantic_chunks", ["embedding_model"], schema="app")
    op.create_index("ix_embedding_jobs_status_created_at", "embedding_jobs", ["status", "created_at"], schema="app")
    op.create_index("ix_retrieval_events_query_run_id_created_at", "retrieval_events", ["query_run_id", "created_at"], schema="app")
    for table_name in ["semantic_documents", "semantic_chunks", "embedding_jobs", "retrieval_events"]:
        _comment(table_name)


def downgrade():
    """移除语义检索表及其索引。"""
    raise RuntimeError("Destructive rollback is disabled; restore a reviewed backup instead.")
