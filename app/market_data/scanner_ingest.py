"""Batch ingestion of daily bars for the Nifty 500 scanner universe.

Uses yfinance (unofficial Yahoo client). Downloads in chunks, upserts into
``scanner_bars``, and reports which symbols returned nothing so coverage is
shown honestly rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

import pandas as pd
from sqlalchemy import delete, select

from app.db.database import get_session
from app.db.models import ScannerBar
from app.services.scanner import BENCHMARK, fetch_universe, load_universe, universe_available

logger = logging.getLogger(__name__)
CHUNK = 50


def _provider_symbol(symbol: str) -> str:
    return "^NSEI" if symbol == BENCHMARK else f"{symbol}.NS"


def _store(session, symbol: str, frame: pd.DataFrame) -> int:
    frame = frame.dropna(subset=["Close", "High", "Low", "Volume"])
    if frame.empty:
        return 0
    rows = {idx.date(): r for idx, r in frame.iterrows()}
    existing = {
        b.date: b
        for b in session.scalars(
            select(ScannerBar).where(ScannerBar.symbol == symbol, ScannerBar.date.in_(list(rows)))
        )
    }
    created = 0
    for d, r in rows.items():
        values = dict(high=float(r["High"]), low=float(r["Low"]), close=float(r["Close"]), volume=int(r["Volume"]))
        bar = existing.get(d)
        if bar is None:
            session.add(ScannerBar(symbol=symbol, date=d, **values))
            created += 1
        else:
            for k, v in values.items():
                setattr(bar, k, v)
    return created


def ingest_universe(period: str = "2y", symbols: list[str] | None = None) -> dict:
    import yfinance as yf

    wanted = symbols or [e.symbol for e in load_universe()]
    wanted = [BENCHMARK] + [s for s in wanted if s != BENCHMARK]
    stored, missing = 0, []
    session = get_session()
    try:
        for i in range(0, len(wanted), CHUNK):
            chunk = wanted[i : i + CHUNK]
            tickers = [_provider_symbol(s) for s in chunk]
            try:
                data = yf.download(
                    tickers, period=period, interval="1d", progress=False, group_by="ticker", threads=True, auto_adjust=False
                )
            except Exception as exc:  # network / provider errors: record, keep going
                logger.warning("scanner chunk failed: %s", exc)
                missing.extend(chunk)
                continue
            for symbol, ticker in zip(chunk, tickers):
                try:
                    frame = data[ticker] if len(tickers) > 1 else data
                    usable = frame.dropna(subset=["Close", "High", "Low", "Volume"])
                    count = _store(session, symbol, frame)
                except (KeyError, ValueError):
                    usable, count = None, 0
                if usable is None or usable.empty:
                    missing.append(symbol)
                stored += count
            session.commit()
    finally:
        session.close()
    return {"requested": len(wanted), "new_rows": stored, "no_data": sorted(set(missing))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Nifty 500 scanner bars.")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--fetch-universe", action="store_true", help="download the NSE Nifty 500 list first")
    parser.add_argument("--limit", type=int, default=0, help="only the first N symbols (testing)")
    args = parser.parse_args()
    if args.fetch_universe:
        print(f"universe rows fetched: {fetch_universe()}")
    elif not universe_available():
        raise SystemExit("Nifty 500 list missing. Re-run with --fetch-universe (a one-time download from NSE Indices).")
    symbols = [e.symbol for e in load_universe()][: args.limit] if args.limit else None
    print(json.dumps(ingest_universe(args.period, symbols), indent=2))


if __name__ == "__main__":
    main()
