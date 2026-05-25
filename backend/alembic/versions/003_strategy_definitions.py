"""strategy definitions

Revision ID: 003
Revises: 002
Create Date: 2026-05-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_strategy_definitions_slug", "strategy_definitions", ["slug"])

    with op.batch_alter_table("backtest_results") as batch_op:
        batch_op.add_column(sa.Column("strategy_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("markers", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("backtest_results") as batch_op:
        batch_op.drop_column("markers")
        batch_op.drop_column("strategy_id")
    op.drop_index("ix_strategy_definitions_slug", table_name="strategy_definitions")
    op.drop_table("strategy_definitions")
