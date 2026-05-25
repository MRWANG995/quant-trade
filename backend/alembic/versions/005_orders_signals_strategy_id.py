"""add strategy_id to orders and signals

Revision ID: 005
Revises: 004
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column("strategy_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_orders_strategy_id",
            "strategy_definitions",
            ["strategy_id"],
            ["id"],
        )
    op.create_index("ix_orders_strategy_id", "orders", ["strategy_id"])

    with op.batch_alter_table("signals") as batch_op:
        batch_op.add_column(
            sa.Column("strategy_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_signals_strategy_id",
            "strategy_definitions",
            ["strategy_id"],
            ["id"],
        )
    op.create_index("ix_signals_strategy_id", "signals", ["strategy_id"])


def downgrade() -> None:
    op.drop_index("ix_signals_strategy_id", "signals")
    with op.batch_alter_table("signals") as batch_op:
        batch_op.drop_constraint("fk_signals_strategy_id", type_="foreignkey")
        batch_op.drop_column("strategy_id")

    op.drop_index("ix_orders_strategy_id", "orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("fk_orders_strategy_id", type_="foreignkey")
        batch_op.drop_column("strategy_id")
