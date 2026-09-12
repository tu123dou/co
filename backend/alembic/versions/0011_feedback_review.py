"""补充回复校对处理字段。

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    """为历史反馈补齐可维护的处理结论和更新时间。"""
    op.add_column("feedbacks", sa.Column("resolution_note", sa.Text()), schema="app")
    op.add_column(
        "feedbacks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="app",
    )
    op.create_check_constraint(
        "ck_feedbacks_status",
        "feedbacks",
        "status IN ('pending', 'resolved')",
        schema="app",
    )
    op.execute("COMMENT ON COLUMN app.feedbacks.resolution_note IS '回复校对时填写的处理说明或核查结论。'")
    op.execute("COMMENT ON COLUMN app.feedbacks.updated_at IS '反馈最后处理时间，包含时区。'")
    op.execute("COMMENT ON COLUMN app.feedbacks.status IS '反馈处理状态；pending 表示待处理，resolved 表示已处理。'")


def downgrade():
    """避免自动丢弃人工处理结论。"""
    raise RuntimeError("Feedback review fields require a reviewed data migration to remove.")
