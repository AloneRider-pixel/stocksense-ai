from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services import scanner as sc


def _bars(closes, volumes=None, spread=0.01):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2025-01-01", periods=n),
            "high": closes * (1 + spread),
            "low": closes * (1 - spread),
            "close": closes,
            "volume": volumes if volumes is not None else np.full(n, 1000.0),
        }
    )


def _uni(*symbols, industry="Tech"):
    return {s: sc.UniverseEntry(s, s.title(), industry) for s in symbols}


def test_universe_csv_loads_and_skips_placeholders(tmp_path):
    csv_file = tmp_path / "u.csv"
    csv_file.write_text(
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        "Alpha Ltd.,Tech,ALPHA,EQ,X1\nDummy Co,Misc,DUMMYONE,EQ,X2\nBeta Ltd.,Banks,BETA,EQ,X3\n"
    )
    uni = sc.load_universe(csv_file)
    assert [e.symbol for e in uni] == ["ALPHA", "BETA"]
    assert uni[0].industry == "Tech"


def test_rs_ranks_stronger_stock_higher_and_skips_short_history():
    n = 300
    bench = _bars(np.linspace(100, 110, n))
    bars = {
        "WIN": _bars(np.linspace(100, 200, n)),
        "MID": _bars(np.linspace(100, 112, n)),
        "LOSE": _bars(np.linspace(100, 70, n)),
        "NEW": _bars(np.linspace(100, 300, 100)),
    }
    rows = sc.relative_strength(bars, bench, _uni(*bars))
    assert [r["symbol"] for r in rows] == ["WIN", "MID", "LOSE"]
    assert rows[0]["rs_rating"] == 99 and rows[-1]["rs_rating"] == 1
    assert "NEW" not in {r["symbol"] for r in rows}


def test_rs_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        sc.RSParams(windows=((63, 0.5), (126, 0.2))).validate()


def test_industry_rotation_detects_improvement():
    n = 320
    bench = _bars(np.linspace(100, 105, n))
    # Industry A turns up only in the last 15 sessions; industry B fades over the same window.
    def turn_up(base):
        return _bars(np.concatenate([np.linspace(100, 100, n - 15), np.linspace(100, base, 15)]))

    def turn_down(base):
        return _bars(np.concatenate([np.linspace(100, 160, n - 15), np.linspace(160, base, 15)]))

    bars, uni = {}, {}
    for i in range(4):
        bars[f"A{i}"] = turn_up(130 + i)
        uni[f"A{i}"] = sc.UniverseEntry(f"A{i}", f"A{i}", "Up")
        bars[f"B{i}"] = turn_down(120 + i)
        uni[f"B{i}"] = sc.UniverseEntry(f"B{i}", f"B{i}", "Down")
    rows = {r["industry"]: r for r in sc.industry_rotation(bars, bench, uni)}
    assert rows["Up"]["change"] > rows["Down"]["change"]


def test_breakout_needs_price_and_volume():
    n = 300
    closes = np.full(n, 100.0)
    closes[-1] = 104.0
    vols = np.full(n, 1000.0)
    vols[-1] = 2500.0
    row = sc.breakouts({"X": _bars(closes, vols)}, _uni("X"))[0]
    assert row["breakout_level"] == pytest.approx(101.0)  # prior high = 100 * 1.01
    assert row["rel_volume"] == pytest.approx(2.5)
    assert row["invalidation_close_below"] == row["breakout_level"]
    vols[-1] = 1200.0  # price breakout on thin volume is not flagged
    assert sc.breakouts({"X": _bars(closes, vols)}, _uni("X")) == []


def test_breakout_excludes_today_from_the_level():
    n = 300
    closes = np.full(n, 100.0)
    closes[-1] = 100.5  # below prior highs of 101
    assert sc.breakouts({"X": _bars(closes, np.r_[np.full(n - 1, 1000.0), 5000.0])}, _uni("X")) == []


def test_explain_has_reasons_and_invalidation_levels():
    n = 300
    bench = _bars(np.linspace(100, 105, n))
    bars = {"A": _bars(np.linspace(100, 180, n)), "B": _bars(np.linspace(100, 90, n))}
    out = sc.explain_stock("A", bars, bench, _uni("A", "B"))
    assert out["reasons"] and out["invalidations"]
    assert all(isinstance(i["level"], float) for i in out["invalidations"])
    assert "prediction" in out["note"].lower()
    assert sc.explain_stock("MISSING", bars, bench, _uni("A")) is None


def test_backtest_has_no_lookahead_and_charges_costs():
    n = 400
    rng = np.random.default_rng(1)
    closes = 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, n))
    df, bench = _bars(closes), _bars(np.linspace(100, 110, n))
    free = sc.backtest_rule(df, bench, sc.RuleSpec(entry="momentum", entry_n=20, entry_threshold_pct=2, cost_bps=0))
    costly = sc.backtest_rule(df, bench, sc.RuleSpec(entry="momentum", entry_n=20, entry_threshold_pct=2, cost_bps=100))
    assert free["trades"] == costly["trades"] > 0
    assert costly["full"]["strategy"]["return_pct"] < free["full"]["strategy"]["return_pct"]
    assert free["out_of_sample"]["strategy"]["days"] > 0
    assert any("survivorship" in a.lower() for a in free["assumptions"])


def test_backtest_rejects_bad_rules():
    df = _bars(np.linspace(100, 120, 400))
    with pytest.raises(ValueError):
        sc.backtest_rule(df, df, sc.RuleSpec(entry="eval"))
    with pytest.raises(ValueError):
        sc.backtest_rule(df, df, sc.RuleSpec(cost_bps=9999))
    with pytest.raises(ValueError):
        sc.backtest_rule(df.head(50), df, sc.RuleSpec())


def test_rs_ties_do_not_crash():
    n = 300
    bench = _bars(np.linspace(100, 110, n))
    same = _bars(np.linspace(100, 150, n))
    rows = sc.relative_strength({"A": same, "B": same.copy()}, bench, _uni("A", "B"))
    assert {r["rs_rating"] for r in rows} == {50}


def test_breadth_counts_and_slippage_lowers_returns():
    n = 300
    up, down = _bars(np.linspace(100, 200, n)), _bars(np.linspace(200, 100, n))
    b = sc.breadth({"U": up, "D": down})
    assert b["pct_above_200dma"] == 50.0 and b["near_52w_high"] == 1 and b["near_52w_low"] == 1
    rng = np.random.default_rng(2)
    df = _bars(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 400)))
    bench = _bars(np.linspace(100, 110, 400))
    spec = dict(entry="momentum", entry_n=20, entry_threshold_pct=2, cost_bps=0)
    a = sc.backtest_rule(df, bench, sc.RuleSpec(slippage_bps=0, **spec))
    b2 = sc.backtest_rule(df, bench, sc.RuleSpec(slippage_bps=50, **spec))
    assert b2["full"]["strategy"]["return_pct"] < a["full"]["strategy"]["return_pct"]


def test_quality_filter_excludes_suspect_series():
    n = 300
    bench = _bars(np.linspace(100, 110, n))
    jump = np.linspace(100, 120, n)
    jump[150:] *= 0.5  # looks like an unadjusted split/demerger
    stale = _bars(np.linspace(100, 120, n - 3))
    bars = {"OK": _bars(np.linspace(100, 140, n)), "JUMP": _bars(jump), "STALE": stale}
    clean, excluded = sc.quality_filter(bars, bench)
    assert set(clean) == {"OK"}
    assert "corporate action" in excluded["JUMP"] and excluded["STALE"].startswith("stale")


def test_changes_flags_new_breakout_and_lost_level():
    n = 320
    bench = _bars(np.linspace(100, 105, n))
    fresh = np.full(n, 100.0)
    fresh[-1] = 105.0
    lost = np.full(n, 100.0)
    lost[-3] = 105.0   # broke out 2 sessions ago ...
    lost[-2:] = 99.0   # ... and is now back under the level
    def vol(spike):
        return np.r_[np.full(n - 3, 1000.0), spike]

    bars = {
        "FRESH": _bars(fresh, np.r_[np.full(n - 1, 1000.0), 3000.0]),
        "LOST": _bars(lost, vol([3000.0, 1000.0, 1000.0])),
    }
    out = sc.changes(bars, bench, _uni("FRESH", "LOST"))
    assert "FRESH" in out["new_breakouts"]
    assert [b["symbol"] for b in out["breakout_levels_lost"]] == ["LOST"]


def test_score_signal_enters_next_session_and_waits_for_bars():
    df = _bars(np.linspace(100, 200, 100))
    bench = _bars(np.linspace(100, 110, 100))
    d = str(df["date"].iloc[10])[:10]
    res = sc.score_signal(d, df, bench)
    c = df["close"]
    assert res["d5"]["return_pct"] == pytest.approx((c.iloc[16] / c.iloc[11] - 1) * 100, abs=0.01)  # entry = day 11, not 10
    assert res["d20"] is not None and res["d60"] is not None
    late = sc.score_signal(str(df["date"].iloc[93])[:10], df, bench)
    assert late["d5"] is not None and late["d20"] is None and late["d60"] is None
    assert sc.score_signal(str(df["date"].iloc[99])[:10], df, bench)["d5"] is None


def test_backtest_ignores_future_bars_and_aligns_benchmark_by_date():
    n = 400
    rng = np.random.default_rng(3)
    closes = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n))
    df = _bars(closes)
    bench = _bars(np.linspace(100, 120, n))
    bench_short = bench.iloc[5:].reset_index(drop=True)  # benchmark missing the first 5 sessions
    spec = sc.RuleSpec(entry="momentum", entry_n=20, entry_threshold_pct=2, cost_bps=0, slippage_bps=0)
    full = sc.backtest_rule(df, bench, spec)
    assert sc.backtest_rule(df, bench_short, spec)["benchmark_days_aligned"] == n - 5
    # Changing bars after day 300 must not change anything that happened before day 300.
    changed = closes.copy()
    changed[300:] *= 1.5
    other = sc.backtest_rule(_bars(changed), bench, spec)
    a = [p for p in full["equity_curve"] if p["date"] < str(df["date"].iloc[299])[:10]]
    b = [p for p in other["equity_curve"] if p["date"] < str(df["date"].iloc[299])[:10]]
    assert a and a == b
