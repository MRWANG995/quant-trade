"""trim default instruments to BTC + XAU + MG7 only

Revision ID: 008
Revises: 007
Create Date: 2026-05-25

把默认品种精简为 9 个：BTC + XAUUSD + Magnificent 7。
原先 7 个（EURUSD/GBPUSD/USDJPY/ES/CL/SPY/QQQ）连同 bars/signals/orders/positions/agent_decisions
全部物理删除。同时 Postgres 上给 assetclass enum 加 'crypto' 值用于 BTC。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OBSOLETE_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "ES", "CL", "SPY", "QQQ")


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Postgres 需要先把 'crypto' 加到 enum，不然后续 seed_instruments 插 BTC 时报
    #    InvalidTextRepresentationError。SQLite 不强校验 enum，跳过即可。
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE assetclass ADD VALUE IF NOT EXISTS 'crypto'")

    # 2) 删除 7 个废弃品种 + 所有外键依赖的数据
    quoted = ",".join(f"'{s}'" for s in OBSOLETE_SYMBOLS)
    sub = f"(SELECT id FROM instruments WHERE symbol IN ({quoted}))"

    # 顺序很重要：子表先于父表
    for table in ("agent_decisions", "bars", "signals", "orders", "positions"):
        op.execute(f"DELETE FROM {table} WHERE instrument_id IN {sub}")
    op.execute(f"DELETE FROM instruments WHERE symbol IN ({quoted})")


def downgrade() -> None:
    # 物理删除的数据无法恢复；Postgres enum 也不易回滚
    pass
