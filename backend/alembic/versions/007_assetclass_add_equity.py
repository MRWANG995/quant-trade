"""add 'equity' to assetclass enum (Postgres)

Revision ID: 007
Revises: 006
Create Date: 2026-05-25

迁移 001 创建 Postgres enum 类型 assetclass 时只放了 forex/metal/futures；
后来项目加入美股（AssetClass.equity）但忘了同步迁移，导致 Postgres 上
seed 美股品种时报 InvalidTextRepresentationError。SQLite 不检查 enum，
所以本地 SQLite 不会出问题。

PostgreSQL 12+ 允许 ALTER TYPE ... ADD VALUE 在事务里，但旧版本要求
脱离事务。用 alembic 的 autocommit_block() 是最稳的写法。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite 不需要任何动作
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE assetclass ADD VALUE IF NOT EXISTS 'equity'")


def downgrade() -> None:
    # Postgres 不支持从 enum 删除值（要重建类型），降级是 no-op。
    pass
