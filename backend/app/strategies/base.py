from dataclasses import dataclass
from datetime import date

from app.models.entities import SignalSide


@dataclass
class StrategySignal:
    symbol: str
    instrument_id: int
    signal_date: date
    side: SignalSide
    strength: float
    reason: str
