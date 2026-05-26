"""add entry/stop_loss/take_profit columns to agent_decisions

Revision ID: 009
Revises: 008
Create Date: 2026-05-26

Agent 策略由"每日一个 long/short/hold 决策"升级为"看盘式"，多输出
具体的入场价 / 止损价 / 止盈价（前端在 K 线图上画 3 条横线）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_decisions") as batch_op:
        batch_op.add_column(sa.Column("entry_price", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("stop_loss", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("take_profit", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_decisions") as batch_op:
        batch_op.drop_column("take_profit")
        batch_op.drop_column("stop_loss")
        batch_op.drop_column("entry_price")
