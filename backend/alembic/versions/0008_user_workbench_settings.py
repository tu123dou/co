"""用户级工作台设置与常见问题统计。

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


STARTER_QUESTIONS = """[
  "今年各经营单元确认收入排名",
  "今年各产品线的收入占比",
  "华东区今年按月收入趋势，与去年同期相比",
  "2026年8月各产品线毛利率",
  "今年各区域收入目标达成率",
  "2026年8月回款额比上个月变化多少"
]"""


def upgrade():
    """创建按用户隔离的配置和问题频次表，并为现有用户写入默认设置。"""
    op.create_table(
        "user_workbench_settings",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="设置所属用户标识，同时作为主键。"),
        sa.Column("welcome_enabled", sa.Boolean(), server_default=sa.true(), nullable=False, comment="是否显示用户配置的开场内容。"),
        sa.Column("welcome_title", sa.String(100), nullable=False, comment="新对话开场标题。"),
        sa.Column("welcome_message", sa.String(500), nullable=False, comment="新对话开场说明文案。"),
        sa.Column(
            "starter_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="有序的开场问题 JSON 数组。",
        ),
        sa.Column("suggestions_enabled", sa.Boolean(), server_default=sa.true(), nullable=False, comment="是否显示下一步问题建议。"),
        sa.Column("common_questions_enabled", sa.Boolean(), server_default=sa.true(), nullable=False, comment="是否显示当前用户的常见问题。"),
        sa.Column("common_question_threshold", sa.Integer(), server_default="3", nullable=False, comment="问题成为常见问题所需的成功次数。"),
        sa.Column("llm_model", sa.String(100), nullable=False, comment="当前用户选择的主大模型。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="设置最后更新时间。"),
        sa.CheckConstraint(
            "common_question_threshold BETWEEN 1 AND 100",
            name="ck_user_workbench_settings_common_threshold",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        schema="app",
        comment="用户工作台设置表。用途：保存每名用户独立的开场内容、快捷提问和主模型配置。粒度：每名用户一行。",
    )
    op.create_table(
        "user_question_stats",
        sa.Column("id", sa.Integer(), primary_key=True, comment="问题统计记录内部唯一标识。"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="统计所属用户标识。"),
        sa.Column("normalized_question", sa.String(1000), nullable=False, comment="用于归并重复提问的标准化文本。"),
        sa.Column("question", sa.String(1000), nullable=False, comment="最近一次成功查询的问题原文。"),
        sa.Column("success_count", sa.Integer(), server_default="1", nullable=False, comment="成功完成问数的累计次数。"),
        sa.Column("last_asked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="最近一次成功查询时间。"),
        sa.CheckConstraint("success_count > 0", name="ck_user_question_stats_success_count"),
        sa.ForeignKeyConstraint(["user_id"], ["app.users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "normalized_question"),
        schema="app",
        comment="用户问题频次表。用途：统计成功问数并生成当前用户自己的常见问题。粒度：每名用户的每个标准化问题一行。",
    )
    op.create_index(
        "ix_user_question_stats_user_id_success_count_last_asked_at",
        "user_question_stats",
        ["user_id", "success_count", "last_asked_at"],
        schema="app",
    )
    op.execute(
        sa.text(
            "INSERT INTO app.user_workbench_settings "
            "(user_id, welcome_title, welcome_message, starter_questions, llm_model) "
            "SELECT id, :title, :message, CAST(:questions AS jsonb), :model FROM app.users "
            "ON CONFLICT (user_id) DO NOTHING"
        ).bindparams(
            title="你好，今天想了解哪些数据？",
            message="从收入趋势到目标达成，用自然语言探索你的经营数据。",
            questions=STARTER_QUESTIONS,
            model="qwen3.8-max",
        )
    )


def downgrade():
    """配置数据不做自动删除，避免误清理用户个性化内容。"""
    raise RuntimeError("User settings are removed only by a reviewed data migration.")
