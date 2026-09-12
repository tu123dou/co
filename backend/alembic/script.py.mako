"""${message}

Alembic 迁移文件模板：新建迁移时自动填入版本关系和升级、回退函数。

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade():
    """把数据库结构升级到当前版本。"""
    ${upgrades if upgrades else "pass"}

def downgrade():
    """把数据库结构回退到上一个版本。"""
    ${downgrades if downgrades else "pass"}
