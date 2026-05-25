"""add agent_decisions table for LLM signal cache

Revision ID: 006
Revises: 005
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),  # long/short/hold
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_output", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategy_definitions.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.UniqueConstraint(
            "strategy_id", "instrument_id", "decision_date",
            name="uq_agent_decision",
        ),
    )
    op.create_index(
        "ix_agent_decisions_strategy_date",
        "agent_decisions",
        ["strategy_id", "decision_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_decisions_strategy_date", "agent_decisions")
    op.drop_table("agent_decisions")
