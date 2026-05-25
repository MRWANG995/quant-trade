from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    strategy_id: Optional[int] = None
    risk_per_trade: float = 0.02
    param_overrides: Optional[dict[str, Any]] = None


class StrategyCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    strategy_type: str = Field(min_length=1, max_length=32)
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    is_default: bool = False


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    strategy_type: Optional[str] = Field(None, min_length=1, max_length=32)
    params: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class StrategyOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    strategy_type: str
    params: dict[str, Any]
    is_active: bool
    is_default: bool

    model_config = {"from_attributes": True}


class InstrumentOut(BaseModel):
    id: int
    symbol: str
    name: str
    asset_class: str
    broker_hint: str
    yfinance_symbol: str

    model_config = {"from_attributes": True}


class BarOut(BaseModel):
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
