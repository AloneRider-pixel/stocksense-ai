"""READ-ONLY report: stored daily bars that the current finality rule would have refused at ingest time.

For every stored bar it re-applies drop_incomplete_bars as of the bar's own ingested_at. If the rule
would have dropped it then, the bar is flagged "possibly partial". It then lists predictions (made on
that bar date, or evaluated against it via actual_date/actual_close) and paper fills (fill_bar_date)
that reference a flagged symbol/date.

LIMITS, printed in the output too:
  * The rule itself is a conservative assumption (see app/market_data/base.py), not a vendor finality flag.
  * A bar that was ingested late and never refreshed may be final yet flagged; a partial bar that was
    refreshed after its session ended is no longer partial and is not flagged. "0 flagged" does not mean
    "none affected".
  * ingested_at is expected to be timezone-aware. Naive values are treated as UTC and counted separately.
Only SELECT statements are issued. Nothing is modified. Run it against a copy or scratch database.
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import select

from app.db.models import MarketBarRecord, PaperOrder, PredictionRecord
from app.market_data.base import MarketBar, drop_incomplete_bars
from app.market_data.symbols import UnsupportedSymbolError, describe_symbol

LIMITS = (
    "ingested_at is set only at first insert (upsert_many does not update it), so it is the FIRST capture time: "
    "a flagged bar may have been corrected by a later refresh, and linked predictions/fills are matched by bar date, "
    "not by when they were made. Heuristic: re-applies today's conservative finality rule as of each bar's ingested_at. "
    "0 flagged does NOT mean none affected (bars refreshed later, or never refreshed, are invisible to it). "
    "The rule is an assumption, not a vendor finality flag."
)


def find_possible_partial(db) -> dict:
    flagged: dict[str, set] = {}
    naive = 0
    total = 0
    unsupported: set[str] = set()
    for row in db.execute(select(MarketBarRecord)).scalars():
        total += 1
        if row.ingested_at is None:
            continue
        ts = row.ingested_at
        if ts.tzinfo is None:
            naive += 1
            ts = ts.replace(tzinfo=timezone.utc)
        try:
            info = describe_symbol(row.symbol)
        except UnsupportedSymbolError:
            unsupported.add(row.symbol)  # counted, not checked: the registry cannot place it
            continue
        bar = MarketBar(symbol=row.symbol, date=row.date.isoformat(), open=row.open, high=row.high,
                        low=row.low, close=row.close, volume=row.volume)
        kept = drop_incomplete_bars([bar], exchange=info.exchange, timezone_name=info.timezone, now=ts)
        if not kept:
            flagged.setdefault(row.symbol, set()).add(row.date)
    predictions = [
        p for p in db.execute(select(PredictionRecord)).scalars()
        if p.prediction_date in flagged.get(p.symbol, ()) or (p.actual_date in flagged.get(p.symbol, ()) and p.actual_close is not None)
    ]
    fills = [o for o in db.execute(select(PaperOrder)).scalars() if o.fill_bar_date in flagged.get(o.symbol, ())]
    return {"bars_checked": total, "naive_ingested_at": naive, "unsupported_symbols": sorted(unsupported), "flagged": flagged,
            "predictions": predictions, "fills": fills, "limits": LIMITS}


def main() -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        r = find_possible_partial(db)
    print(r["limits"])
    print(f"bars checked: {r['bars_checked']} (naive ingested_at treated as UTC: {r['naive_ingested_at']})")
    print(f"stored symbols skipped as unsupported suffixes (not checked): {r['unsupported_symbols']}")
    for sym, dates in sorted(r["flagged"].items()):
        print(f"  possibly partial {sym}: {len(dates)} bar(s), {min(dates)}..{max(dates)}")
    print(f"predictions referencing a flagged bar (made on it, or evaluated against it): {len(r['predictions'])}")
    print(f"paper fills using a flagged bar date: {len(r['fills'])}")


if __name__ == "__main__":
    main()
