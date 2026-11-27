from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MarketBar:
    date: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataProvider(Protocol):
    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        ...


# Local hour after which a same-day daily bar from an exchange-traded market is treated as
# final. These cutoffs are assumptions with a margin over the usual close (NSE 15:30 IST,
# US 16:00 ET); they are not vendor-published finality flags.
_FINAL_AFTER_LOCAL_HOUR = {"NSE": 16, "NSE Index": 16, "US": 17}
# Instruments with no single session (spot metals, FX, or an unknown venue) are handled
# conservatively: the current UTC date is never final, and the previous UTC date is also
# held back until 22:00 UTC (after a 17:00 New York close in either DST state). Vendor
# date conventions for these were NOT verified; this only errs toward dropping more.
_ROLLING_HOLD_UNTIL_UTC_HOUR = 22


def drop_incomplete_bars(bars: list[MarketBar], *, exchange: str, timezone_name: str, now=None) -> list[MarketBar]:
    """Drop bars whose session may still be running or may not be final.

    Providers return the running session as today's bar with close = last price. Storing it
    as a daily close and overwriting it on refresh makes prices, paper-wallet fills,
    backtests and predictions use a moving value. This is defensive filtering, not a
    guarantee that the remaining bars are final.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    utc_now = (now or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo("UTC"))
    final_hour = _FINAL_AFTER_LOCAL_HOUR.get(exchange)
    if final_hour is None:
        today = utc_now.date()
        newest_allowed = today - timedelta(days=1 if utc_now.hour >= _ROLLING_HOLD_UNTIL_UTC_HOUR else 2)
        return [b for b in bars if b.date <= newest_allowed.isoformat()]
    local_now = utc_now.astimezone(ZoneInfo(timezone_name))
    today = local_now.date().isoformat()
    session_over = local_now.hour >= final_hour and local_now.weekday() < 5
    return [b for b in bars if b.date < today or (b.date == today and session_over)]
