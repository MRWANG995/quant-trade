"""backtest metrics column + risk_free_rates table

Revision ID: 004
Revises: 003
Create Date: 2026-05-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_results") as batch_op:
        batch_op.add_column(sa.Column("metrics", sa.JSON(), nullable=True))

    op.create_table(
        "risk_free_rates",
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("as_of_date"),
    )


def downgrade() -> None:
    op.drop_table("risk_free_rates")
    with op.batch_alter_table("backtest_results") as batch_op:
        batch_op.drop_column("metrics")
