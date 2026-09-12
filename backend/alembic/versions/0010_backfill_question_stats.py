"""从历史成功问数回填个人常见问题频次。

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    """按会话消息顺序匹配用户问题与紧随其后的成功助手回答。"""
    op.execute(
        r"""
        WITH ordered AS (
            SELECT
                c.user_id,
                m.content,
                m.role,
                m.created_at,
                LEAD(m.role) OVER message_order AS next_role,
                LEAD(m.result) OVER message_order AS next_result
            FROM app.messages AS m
            JOIN app.conversations AS c ON c.id = m.conversation_id
            WINDOW message_order AS (
                PARTITION BY m.conversation_id
                ORDER BY m.created_at, m.id
            )
        ), successful AS (
            SELECT
                user_id,
                btrim(content) AS question,
                lower(
                    regexp_replace(
                        rtrim(btrim(content), '。！？!?；;，, '),
                        '\s+',
                        ' ',
                        'g'
                    )
                ) AS normalized_question,
                created_at
            FROM ordered
            WHERE role = 'user'
              AND next_role = 'assistant'
              AND next_result->>'status' = 'success'
        ), aggregated AS (
            SELECT
                user_id,
                normalized_question,
                (array_agg(question ORDER BY created_at DESC))[1] AS question,
                count(*)::integer AS success_count,
                max(created_at) AS last_asked_at
            FROM successful
            WHERE normalized_question <> ''
            GROUP BY user_id, normalized_question
        )
        INSERT INTO app.user_question_stats (
            user_id,
            normalized_question,
            question,
            success_count,
            last_asked_at
        )
        SELECT
            user_id,
            normalized_question,
            question,
            success_count,
            last_asked_at
        FROM aggregated
        ON CONFLICT (user_id, normalized_question) DO UPDATE
        SET
            question = CASE
                WHEN EXCLUDED.last_asked_at >= app.user_question_stats.last_asked_at
                    THEN EXCLUDED.question
                ELSE app.user_question_stats.question
            END,
            success_count = greatest(
                app.user_question_stats.success_count,
                EXCLUDED.success_count
            ),
            last_asked_at = greatest(
                app.user_question_stats.last_asked_at,
                EXCLUDED.last_asked_at
            )
        """
    )


def downgrade():
    """无法区分历史回填与上线后新增统计，因此不自动删除数据。"""
    raise RuntimeError("Question statistics are reverted only by a reviewed data migration.")
