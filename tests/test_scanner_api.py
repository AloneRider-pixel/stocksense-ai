from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

import app.api.scanner_routes as scanner_routes
from app.db.models import ScannerBar


@pytest.fixture(autouse=True)
def _reset(monkeypatch, session_factory, tmp_path):
    monkeypatch.setattr(scanner_routes, "get_session", session_factory)
    universe = tmp_path / "u.csv"
    universe.write_text(
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        + "".join(f"{s} Ltd.,Tech,{s},EQ,X{i}\n" for i, s in enumerate(["RELIANCE", "TCS", "INFY"]))
    )
    monkeypatch.setattr(scanner_routes.sc, "UNIVERSE_CSV", universe)
    monkeypatch.setattr(scanner_routes.settings, "scanner_enabled", True)
    scanner_routes._ingest.update({"running": False, "last": None, "last_started": None})
    scanner_routes._cache.update({"data": None, "expires": 0.0})
    yield
    scanner_routes._cache.update({"data": None, "expires": 0.0})


def _seed(session_factory, symbols):
    session = session_factory()
    start = date(2025, 1, 1)
    for k, symbol in enumerate(symbols):
        base = 100.0
        for i in range(321):
            base *= 1 + ((0.0005 + 0.0007 * k) if k else 0.0003)
            session.add(ScannerBar(symbol=symbol, date=start + timedelta(days=i), high=base * 1.01, low=base * 0.99, close=base, volume=1000))
    session.commit()
    session.close()


def test_scanner_requires_auth(client):
    assert client.get("/api/v1/scanner/rs").status_code in (401, 403)


def test_rs_returns_503_until_data_loaded(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/v1/scanner/rs", headers=headers)
    assert r.status_code == 503
    assert "SCANNER_DATA_NOT_LOADED" in r.text


def test_coverage_endpoint_reports_honest_counts(client, auth_headers):
    headers, _ = auth_headers
    body = client.get("/api/v1/scanner/coverage", headers=headers).json()
    assert body["symbols_with_data"] == 0 and body["benchmark_loaded"] is False
    assert body["universe_size"] == 3 and body["refresh_enabled"] is False


def test_rs_and_explain_and_backtest_with_data(client, auth_headers, session_factory):
    headers, _ = auth_headers
    _seed(session_factory, ["NIFTY50", "RELIANCE", "TCS", "INFY"])
    rs = client.get("/api/v1/scanner/rs", headers=headers).json()
    assert rs["ranked"] == 3 and "StockSense's own formula" in rs["method"]
    explain = client.get("/api/v1/scanner/stock/RELIANCE", headers=headers)
    assert explain.status_code == 200 and explain.json()["invalidations"]
    assert client.get("/api/v1/scanner/stock/NOPE", headers=headers).status_code == 404
    bt = client.post("/api/v1/scanner/backtest", json={"symbol": "RELIANCE", "entry": "momentum", "entry_n": 20, "entry_threshold_pct": 1}, headers=headers)
    assert bt.status_code == 200 and "out_of_sample" in bt.json()
    bad = client.post("/api/v1/scanner/backtest", json={"symbol": "RELIANCE", "entry": "os.system"}, headers=headers)
    assert bad.status_code == 422


def test_refresh_is_off_by_default_and_limited_when_on(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    assert client.post("/api/v1/scanner/refresh", headers=headers).status_code == 403
    monkeypatch.setattr(scanner_routes.settings, "scanner_refresh_enabled", True)
    monkeypatch.setattr("app.market_data.scanner_ingest.ingest_universe", lambda: {"requested": 0})
    first = client.post("/api/v1/scanner/refresh", headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "started"
    import time
    for _ in range(50):
        if not scanner_routes._ingest["running"]:
            break
        time.sleep(0.05)
    assert client.post("/api/v1/scanner/refresh", headers=headers).status_code == 429


def test_scanner_disabled_by_default(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr(scanner_routes.settings, "scanner_enabled", False)
    for path in ("coverage", "rs", "industries", "breadth", "breakouts", "changes", "scorecard", "stock/TCS"):
        assert client.get(f"/api/v1/scanner/{path}", headers=headers).status_code == 403, path
    assert client.post("/api/v1/scanner/backtest", json={"symbol": "TCS"}, headers=headers).status_code == 403
    assert client.post("/api/v1/scanner/refresh", headers=headers).status_code == 403


def _extend(session_factory, symbols, days):
    session = session_factory()
    last = max(b.date for b in session.query(ScannerBar).filter(ScannerBar.symbol == "NIFTY50"))
    for k, symbol in enumerate(symbols):
        base = session.query(ScannerBar).filter(ScannerBar.symbol == symbol).order_by(ScannerBar.date.desc()).first().close
        for i in range(1, days + 1):
            base *= 1 + ((0.0005 + 0.0007 * k) if k else 0.0003)
            session.add(ScannerBar(symbol=symbol, date=last + timedelta(days=i), high=base * 1.01, low=base * 0.99, close=base, volume=1000))
    session.commit()
    session.close()


IST = ZoneInfo("Asia/Kolkata")


def _ist(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=IST).astimezone(timezone.utc)


def test_classify_run_forward_rules():
    sc = scanner_routes.sc
    mon, fri = date(2025, 11, 17), date(2025, 11, 14)
    assert sc.classify_run(_ist(2025, 11, 17, 17), mon, True)[0] == "forward"  # prompt, after close
    assert sc.entry_not_before(_ist(2025, 11, 17, 17)) == date(2025, 11, 18)  # strictly after observation date
    assert sc.classify_run(_ist(2025, 11, 15, 11), fri, True)[0] == "forward"  # weekend observation of Friday bar
    assert sc.entry_not_before(_ist(2025, 11, 15, 11)) == mon  # Saturday -> Monday entry
    assert sc.classify_run(_ist(2025, 11, 18, 10), mon, True)[0] == "forward"  # delayed to next morning, before entry session close
    assert sc.entry_not_before(_ist(2025, 11, 18, 10)) == date(2025, 11, 19)
    assert sc.classify_run(_ist(2025, 11, 18, 17), mon, True)[0] == "retrospective"  # observed after the entry session closed
    assert sc.classify_run(_ist(2025, 11, 19, 10), mon, True)[0] == "retrospective"  # multi-day outage
    assert sc.classify_run(_ist(2025, 11, 17, 17), fri, True)[0] == "retrospective"  # newer than last run but stale bar
    assert sc.classify_run(_ist(2025, 11, 17, 15, 45), mon, True)[0] == "retrospective"  # bar not yet final
    assert sc.classify_run(_ist(2025, 11, 17, 17), mon, False)[0] == "retrospective"  # backfill / recompute


def test_scorecard_retrospective_vs_forward_provenance(client, auth_headers, session_factory, monkeypatch):
    headers, _ = auth_headers
    syms = ["NIFTY50", "RELIANCE", "TCS", "INFY"]
    _seed(session_factory, syms)
    card = client.get("/api/v1/scanner/scorecard", headers=headers).json()
    assert card["forward_signals"] == 0 and card["retrospective_signals"] == 0 and card["runs"] == []
    # Recomputed/backfilled run on the first bar date: retrospective even though it is "latest".
    first = scanner_routes.log_current_signals(observed_at=_ist(2025, 11, 17, 17), live=False)
    assert first > 0 and scanner_routes.log_current_signals(observed_at=_ist(2025, 11, 17, 18)) == 0  # same bar date: no re-observation
    card = client.get("/api/v1/scanner/scorecard", headers=headers).json()
    assert card["retrospective_signals"] == first and card["forward_signals"] == 0
    assert card["runs"][0]["origin"] == "retrospective" and card["runs"][0]["formula_version"] and card["runs"][0]["origin_reason"]
    assert all(r["origin"] == "retrospective" and r["inputs"]["raw"]["source"] for r in card["recent"])
    assert all(v == {"scored": 0} for kinds in card["summary_forward_only"].values() for v in kinds.values())
    # Newer bar date observed after a multi-day outage (stale): still retrospective.
    _extend(session_factory, syms, 7)
    scanner_routes._cache.update({"data": None, "expires": 0.0})
    assert scanner_routes.log_current_signals(observed_at=_ist(2025, 11, 26, 10)) > 0
    assert [r["origin"] for r in client.get("/api/v1/scanner/scorecard", headers=headers).json()["runs"]] == ["retrospective", "retrospective"]
    # Prompt live run on a newer bar date: forward; entry is strictly after observation.
    _extend(session_factory, syms, 63)
    scanner_routes._cache.update({"data": None, "expires": 0.0})
    obs = _ist(2026, 1, 26, 17)  # Monday after close
    assert scanner_routes.log_current_signals(observed_at=obs) > 0
    card = client.get("/api/v1/scanner/scorecard", headers=headers).json()
    assert card["forward_signals"] > 0
    assert card["runs"][0]["origin"] == "forward" and card["runs"][0]["entry_not_before"] == "2026-01-27"
    fwd = [r for r in card["recent"] if r["origin"] == "forward"]
    assert fwd and all(r["entry_not_before"] == "2026-01-27" for r in fwd)
    # Rule change: old rows are labelled superseded and leave the headline, not rewritten.
    monkeypatch.setattr(scanner_routes.sc, "FORMULA_VERSION", "rs2-test")
    card = client.get("/api/v1/scanner/scorecard", headers=headers).json()
    assert all(r["status"].startswith("superseded") for r in card["recent"])
    assert all(v == {"scored": 0} for kinds in card["summary_forward_only"].values() for v in kinds.values())
    assert client.get("/api/v1/scanner/changes", headers=headers).status_code == 200


def test_score_signal_enters_after_observation_not_after_bar():
    import pandas as pd
    sc = scanner_routes.sc
    dates = pd.bdate_range("2025-11-03", periods=12)
    df = pd.DataFrame({"date": dates, "close": [float(100 + i) for i in range(12)]})
    # Signal bar index 2; observed late so entry floor is index 5: horizon counts from there.
    res = sc.score_signal(str(dates[2].date()), df, df, horizons=(5,), entry_floor=str(dates[5].date()))
    assert res["d5"]["return_pct"] == round((110 / 105 - 1) * 100, 2)
    res = sc.score_signal(str(dates[2].date()), df, df, horizons=(5,))
    assert res["d5"]["return_pct"] == round((108 / 103 - 1) * 100, 2)


def test_score_signal_uses_actual_bars_across_holiday_and_missing_entry():
    import pandas as pd
    sc = scanner_routes.sc
    dates = [d for d in pd.bdate_range("2025-11-03", periods=14) if d != pd.Timestamp("2025-11-10")]  # Mon 10th is a holiday: no bar
    df = pd.DataFrame({"date": dates, "close": [float(100 + i) for i in range(len(dates))]})
    fri = str(pd.Timestamp("2025-11-07").date())
    # Observed Friday: floor is the (holiday) Monday; entry is the next ACTUAL bar (Tue 11th), horizon counts bars.
    res = sc.score_signal(fri, df, df, horizons=(3,), entry_floor="2025-11-10")
    i = list(df["date"]).index(pd.Timestamp("2025-11-11"))
    assert res["d3"]["return_pct"] == round((df["close"].iloc[i + 3] / df["close"].iloc[i] - 1) * 100, 2)
    # Stock has no bar on the entry day while the benchmark does: not scored, nothing invented.
    stock = df[df["date"] != pd.Timestamp("2025-11-11")].reset_index(drop=True)
    bench = df
    assert sc.score_signal(fri, stock, bench, horizons=(3,), entry_floor="2025-11-10")["d3"] is None
    # Floor beyond available data: pending.
    assert sc.score_signal(fri, df, df, horizons=(3,), entry_floor="2026-03-02")["d3"] is None
