"""用户独立的自定义模型配置与加密凭据。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_workbench_settings", sa.Column(
        "custom_model_id", sa.String(36), nullable=True,
        comment="当前选择的用户自定义模型标识；为空时使用内置模型。",
    ), schema="app")
    op.add_column("user_workbench_settings", sa.Column(
        "custom_models", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"),
        comment="用户自定义模型配置数组；API Key 仅保存认证加密密文，不对浏览器返回。",
    ), schema="app")


def downgrade():
    raise RuntimeError("删除模型凭据需要人工审查与备份，不支持自动回退。")
