"""自定义模型采用完整 URL，并增加 API 格式与展示名称；保留旧配置及密文。"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE app.user_workbench_settings AS settings
        SET custom_models = (
            SELECT jsonb_agg(
                (item - 'base_url') || jsonb_build_object(
                    'request_url', COALESCE(item->>'request_url', rtrim(item->>'base_url', '/') || '/chat/completions'),
                    'api_format', COALESCE(item->>'api_format', 'openai'),
                    'display_name', COALESCE(NULLIF(item->>'display_name', ''), item->>'model_name')
                ) ORDER BY position
            )
            FROM jsonb_array_elements(settings.custom_models) WITH ORDINALITY AS models(item, position)
        )
        WHERE jsonb_array_length(custom_models) > 0
    """)


def downgrade():
    raise RuntimeError("协议配置不能无损转换为旧 Base URL，禁止自动回退。")
