from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, ScannerBar
from app.market_data.scanner_ingest import _store


def _frame(dates):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"High": 11.0, "Low": 9.0, "Close": 10.0, "Volume": 1000}, index=idx)


def _stored(now):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[ScannerBar.__table__])
    with Session(engine) as session:
        _store(session, "INFY", _frame(["2026-11-25", "2026-11-26"]), now=now)
        session.flush()
        return sorted(b.date.isoformat() for b in session.scalars(select(ScannerBar)))


def test_scanner_store_skips_the_running_nse_session_bar_and_keeps_it_after_the_cutoff():
    ist = ZoneInfo("Asia/Kolkata")
    assert _stored(datetime(2026, 11, 26, 11, 0, tzinfo=ist)) == ["2026-11-25"]
    assert _stored(datetime(2026, 11, 26, 16, 30, tzinfo=ist)) == ["2026-11-25", "2026-11-26"]


def test_scanner_store_handles_tz_aware_index_and_empty_frames():
    ist = ZoneInfo("Asia/Kolkata")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[ScannerBar.__table__])
    idx = pd.DatetimeIndex(["2026-11-25", "2026-11-26"], tz="Asia/Kolkata")  # yfinance-style tz-aware index
    frame = pd.DataFrame({"High": 11.0, "Low": 9.0, "Close": 10.0, "Volume": 1000}, index=idx)
    with Session(engine) as session:
        assert _store(session, "INFY", frame, now=datetime(2026, 11, 26, 11, 0, tzinfo=ist)) == 1
        assert _store(session, "INFY", frame.iloc[0:0], now=datetime(2026, 11, 26, 11, 0, tzinfo=ist)) == 0
        session.flush()
        assert sorted(b.date.isoformat() for b in session.scalars(select(ScannerBar))) == ["2026-11-25"]
