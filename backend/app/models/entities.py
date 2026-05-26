import enum
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetClass(str, enum.Enum):
    forex = "forex"
    metal = "metal"
    futures = "futures"
    equity = "equity"
    crypto = "crypto"


class BrokerHint(str, enum.Enum):
    paper = "paper"
    oanda = "oanda"
    ib = "ib"


class SignalSide(str, enum.Enum):
    long = "long"
    short = "short"
    flat = "flat"


class OrderSide(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    yfinance_symbol: Mapped[str] = mapped_column(String(32))
    asset_class: Mapped[AssetClass] = mapped_column(Enum(AssetClass))
    broker_hint: Mapped[BrokerHint] = mapped_column(Enum(BrokerHint))
    pip_value: Mapped[float] = mapped_column(Float, default=0.0001)
    contract_size: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(default=True)

    bars: Mapped[list["Bar"]] = relationship(back_populates="instrument")
    signals: Mapped[list["Signal"]] = relationship(back_populates="instrument")
    orders: Mapped[list["Order"]] = relationship(back_populates="instrument")
    positions: Mapped[list["Position"]] = relationship(back_populates="instrument")


class Bar(Base):
    __tablename__ = "bars"
    __table_args__ = (UniqueConstraint("instrument_id", "trade_date", name="uq_bar_instrument_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)

    instrument: Mapped["Instrument"] = relationship(back_populates="bars")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_definitions.id"), nullable=True, index=True
    )
    signal_date: Mapped[date] = mapped_column(Date, index=True)
    side: Mapped[SignalSide] = mapped_column(Enum(SignalSide))
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    executed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="signals")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_definitions.id"), nullable=True, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, index=True)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    quantity: Mapped[float] = mapped_column(Float)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    broker: Mapped[str] = mapped_column(String(32), default="paper")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="orders")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    instrument: Mapped["Instrument"] = relationship(back_populates="positions")


class StrategyDefinition(Base):
    __tablename__ = "strategy_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    strategy_type: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_definitions.id"), nullable=True, index=True
    )
    strategy: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    initial_capital: Mapped[float] = mapped_column(Float)
    final_equity: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    max_drawdown_pct: Mapped[float] = mapped_column(Float)
    trade_count: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    equity_curve: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    trades: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    markers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RiskFreeRate(Base):
    """美国 3 月期国债年化收益率，按日缓存（FRED DGS3MO）。"""

    __tablename__ = "risk_free_rates"

    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rate: Mapped[float] = mapped_column(Float)  # 年化小数，如 0.045
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    run_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentDecision(Base):
    """LLM Agent 策略对（strategy, instrument, date）的一次决策缓存。"""
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_definitions.id"), index=True
    )
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    decision_date: Mapped[date] = mapped_column(Date)
    side: Mapped[str] = mapped_column(String(8))  # long/short/hold
    confidence: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, default="")
    # 看盘式 Agent 的具体价位（可空，旧决策没有这些字段）
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_output: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
