from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

SWARM = "stocks.example.market"
EXCHANGE = os.getenv("SYNAPSE_EXCHANGE", "127.0.0.1:9100")
MARKET_TZ = ZoneInfo("America/New_York")


def seed() -> tuple[str, int]:
    host, port = EXCHANGE.rsplit(":", 1)
    return host, int(port)


def market_is_open(now: datetime | None = None) -> bool:
    current = now.astimezone(MARKET_TZ) if now else datetime.now(MARKET_TZ)
    if current.weekday() >= 5:
        return False
    open_time = current.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = current.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= current <= close_time
