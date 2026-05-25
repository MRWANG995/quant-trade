from datetime import date


def bars_to_records(bars) -> list[dict]:
    return [
        {
            "trade_date": b.trade_date if hasattr(b, "trade_date") else b["trade_date"],
            "open": b.open if hasattr(b, "open") else b["open"],
            "high": b.high if hasattr(b, "high") else b["high"],
            "low": b.low if hasattr(b, "low") else b["low"],
            "close": b.close if hasattr(b, "close") else b["close"],
            "volume": b.volume if hasattr(b, "volume") else b.get("volume", 0),
        }
        for b in bars
    ]


def parse_trade_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
