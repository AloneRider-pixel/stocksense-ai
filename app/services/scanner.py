"""Nifty 500 scanner: relative strength, industry rotation, breakouts, rule backtests.

Everything is computed from stored daily bars. The formulas are StockSense's
own, fully disclosed and configurable (see ``RSParams`` / ``BreakoutParams``);
they are not a standard or canonical rating. Output is descriptive: it says
what the numbers are today, never what a stock will do.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
SESSION_SETTLE = time(16, 0)  # NSE closes 15:30 IST; bars are treated as final only after 16:00 IST
DATA_SOURCE = "yfinance auto_adjust=False (split-adjusted OHLC, no dividends)"


def _prev_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def expected_last_session(observed_at: datetime) -> date:
    """Most recent weekday session whose bar should be final at observed_at (IST). Exchange holidays are not modelled."""
    local = observed_at.astimezone(IST)
    if local.weekday() < 5 and local.time() >= SESSION_SETTLE:
        return local.date()
    return _prev_weekday(local.date())


def entry_not_before(observed_at: datetime) -> date:
    """First weekday session strictly after the observation date (IST). Entry is that session's close."""
    return _next_weekday(observed_at.astimezone(IST).date())


def classify_run(observed_at: datetime, as_of: date, live: bool) -> tuple[str, str]:
    """"forward" only for a live run observed promptly after the as_of bar and before its entry session."""
    if not live:
        return "retrospective", "imported, backfilled or recomputed run"
    if as_of != expected_last_session(observed_at):
        return "retrospective", f"stale: bar date {as_of} is not the latest completed session at observation time"
    return "forward", "live run on the latest completed session"


FORMULA_VERSION = "rs1-breakout1-gate1"  # bump whenever a formula, default or data check changes
UNIVERSE_CSV = Path(__file__).resolve().parents[2] / "data" / "nifty500_constituents.csv"
BENCHMARK = "NIFTY50"
TRADING_DAYS_PER_MONTH = 21


@dataclass(frozen=True)
class UniverseEntry:
    symbol: str
    name: str
    industry: str


UNIVERSE_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"


def universe_available(path: Path | None = None) -> bool:
    return (path or UNIVERSE_CSV).exists()


def fetch_universe(path: Path | None = None, timeout: float = 30.0) -> int:
    """Download NSE Indices' public Nifty 500 constituent list to ``path`` (one explicit fetch).

    The file is deliberately not committed to the repository: its redistribution
    terms have not been verified.
    """
    import urllib.request

    path = path or UNIVERSE_CSV

    request = urllib.request.Request(UNIVERSE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        text = response.read().decode("utf-8-sig")
    if not text.startswith("Company Name"):
        raise ValueError("Unexpected response while fetching the Nifty 500 list")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text.count("\n") - 1


def load_universe(path: Path | None = None) -> list[UniverseEntry]:
    """Read the vendored NSE Indices Nifty 500 constituent snapshot.

    The file's column is NSE's *Industry* classification, so it is surfaced as
    "industry", not sector.
    """
    with (path or UNIVERSE_CSV).open(newline="", encoding="utf-8") as handle:
        return [
            UniverseEntry(row["Symbol"].strip().upper(), row["Company Name"].strip(), row["Industry"].strip())
            for row in csv.DictReader(handle)
            if row.get("Symbol") and not row["Symbol"].strip().upper().startswith("DUMMY")
        ]


MAX_DAILY_MOVE = 0.25  # a larger one-day move in the last year is treated as a possible unadjusted corporate action


def quality_filter(
    bars: dict[str, pd.DataFrame], bench: pd.DataFrame | None
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Drop series that cannot be trusted for ranking, with the reason for each.

    Checks: stale last bar vs the benchmark, non-positive or inconsistent OHLC,
    more than 5 benchmark sessions missing inside the stock's own date range, and any single-day move over
    25% in the last 252 sessions (possible split/demerger/bonus not adjusted by
    the provider; a genuine move would also be excluded, which is the safe side).

    This is a data-sanity guardrail, NOT corporate-action validation: it can
    exclude real jumps and can miss smaller unadjusted events (e.g. a 15% drop).
    """
    clean: dict[str, pd.DataFrame] = {}
    excluded: dict[str, str] = {}
    bench_dates = set(pd.to_datetime(bench["date"]).dt.date) if bench is not None else set()
    bench_last = max(bench_dates) if bench_dates else None
    for symbol, df in bars.items():
        if len(df) < 2:
            excluded[symbol] = "too little history"
            continue
        close = df["close"].astype(float).to_numpy()
        high, low = df["high"].astype(float).to_numpy(), df["low"].astype(float).to_numpy()
        dates = pd.to_datetime(df["date"]).dt.date
        if bench_last is not None and dates.iloc[-1] < bench_last:
            excluded[symbol] = "stale: last bar older than benchmark"
        elif (close <= 0).any() or (high < low).any() or (close > high * 1.001).any() or (close < low * 0.999).any():
            excluded[symbol] = "inconsistent or non-positive prices"
        elif bench_dates and sum(1 for d in bench_dates if dates.iloc[0] <= d <= dates.iloc[-1] and d not in set(dates)) > 5:
            excluded[symbol] = "missing sessions vs benchmark"
        else:
            moves = np.abs(close[1:] / close[:-1] - 1)[-252:]
            if len(moves) and moves.max() > MAX_DAILY_MOVE:
                excluded[symbol] = f"one-day move of {moves.max() * 100:.0f}% (possible unadjusted corporate action)"
            else:
                clean[symbol] = df
    return clean, excluded


@dataclass(frozen=True)
class RSParams:
    # trading-day lookback -> weight. Default: 3m 40%, 6m 30%, 12m 30%.
    windows: tuple[tuple[int, float], ...] = ((63, 0.4), (126, 0.3), (252, 0.3))
    rotation_lookback_days: int = 20

    def validate(self) -> None:
        if not self.windows or abs(sum(w for _, w in self.windows) - 1.0) > 1e-6:
            raise ValueError("RS window weights must sum to 1")


@dataclass(frozen=True)
class BreakoutParams:
    lookback_days: int = 55
    min_rel_volume: float = 1.5
    max_pct_below_52w_high: float | None = None


def _closes(df: pd.DataFrame) -> pd.Series:
    return df["close"].astype(float).reset_index(drop=True)


def blended_excess_return(
    close: pd.Series, bench: pd.Series, params: RSParams, offset: int = 0
) -> float | None:
    """Weighted excess return vs the benchmark, as of ``offset`` bars ago.

    Returns None when history is shorter than the longest window.
    """
    longest = max(w for w, _ in params.windows)
    end = len(close) - 1 - offset
    bend = len(bench) - 1 - offset
    if end - longest < 0 or bend - longest < 0:
        return None
    total = 0.0
    for window, weight in params.windows:
        stock_ret = close.iloc[end] / close.iloc[end - window] - 1.0
        bench_ret = bench.iloc[bend] / bench.iloc[bend - window] - 1.0
        total += weight * (stock_ret - bench_ret)
    return float(total)


def _percentile_rank(scores: dict[str, float]) -> dict[str, int]:
    """Rank scores into 1..99 percentiles (99 = strongest)."""
    if not scores:
        return {}
    series = pd.Series(scores)
    pct = series.rank(method="average", pct=True)
    if len(series) == 1 or pct.max() == pct.min():
        return {k: 50 for k in series.index}
    scaled = 1 + (pct - pct.min()) / (pct.max() - pct.min()) * 98
    return {k: int(round(v)) for k, v in scaled.items()}


def relative_strength(
    bars: dict[str, pd.DataFrame],
    bench: pd.DataFrame,
    universe: dict[str, UniverseEntry],
    params: RSParams = RSParams(),
    offset: int = 0,
) -> list[dict]:
    params.validate()
    bclose = _closes(bench)
    scores: dict[str, float] = {}
    returns: dict[str, dict[int, float]] = {}
    for symbol, df in bars.items():
        close = _closes(df)
        score = blended_excess_return(close, bclose, params, offset)
        if score is None:
            continue
        scores[symbol] = score
        end = len(close) - 1 - offset
        returns[symbol] = {w: float(close.iloc[end] / close.iloc[end - w] - 1.0) for w, _ in params.windows}
    ranks = _percentile_rank(scores)
    rows = []
    for symbol, score in scores.items():
        entry = universe.get(symbol)
        rows.append(
            {
                "symbol": symbol,
                "name": entry.name if entry else symbol,
                "industry": entry.industry if entry else None,
                "rs_rating": ranks[symbol],
                "excess_return_pct": round(score * 100, 2),
                "returns_pct": {str(w): round(r * 100, 2) for w, r in returns[symbol].items()},
            }
        )
    rows.sort(key=lambda r: (-r["rs_rating"], -r["excess_return_pct"]))
    return rows


def industry_rotation(
    bars: dict[str, pd.DataFrame],
    bench: pd.DataFrame,
    universe: dict[str, UniverseEntry],
    params: RSParams = RSParams(),
    min_members: int = 3,
) -> list[dict]:
    """Median RS rating per industry now vs ``rotation_lookback_days`` ago."""
    now_rows = relative_strength(bars, bench, universe, params, 0)
    then_rows = relative_strength(bars, bench, universe, params, params.rotation_lookback_days)

    def medians(rows: list[dict]) -> dict[str, tuple[float, int]]:
        groups: dict[str, list[int]] = {}
        for r in rows:
            if r["industry"]:
                groups.setdefault(r["industry"], []).append(r["rs_rating"])
        return {k: (float(np.median(v)), len(v)) for k, v in groups.items() if len(v) >= min_members}

    now_m, then_m = medians(now_rows), medians(then_rows)
    rows = []
    for industry, (median_now, members) in now_m.items():
        prev = then_m.get(industry)
        rows.append(
            {
                "industry": industry,
                "members": members,
                "median_rs_now": round(median_now, 1),
                "median_rs_before": round(prev[0], 1) if prev else None,
                "change": round(median_now - prev[0], 1) if prev else None,
            }
        )
    rows.sort(key=lambda r: (r["change"] is None, -(r["change"] or 0)))
    return rows


def _breakout_row(symbol: str, df: pd.DataFrame, p: BreakoutParams) -> dict | None:
    n = p.lookback_days
    if len(df) < max(n + 1, 253):
        return None
    close = df["close"].astype(float).to_numpy()
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    vol = df["volume"].astype(float).to_numpy()
    level = float(high[-n - 1 : -1].max())  # prior N-day high, excluding today
    last = float(close[-1])
    avg_vol = float(vol[-21:-1].mean())
    rel_vol = float(vol[-1] / avg_vol) if avg_vol > 0 else 0.0
    high_52w = float(high[-252:].max())
    pct_below_52w = (high_52w - last) / high_52w * 100
    if last <= level or rel_vol < p.min_rel_volume:
        return None
    if p.max_pct_below_52w_high is not None and pct_below_52w > p.max_pct_below_52w_high:
        return None
    return {
        "symbol": symbol,
        "date": str(df["date"].iloc[-1])[:10],
        "close": round(last, 2),
        "breakout_level": round(level, 2),
        "pct_above_level": round((last / level - 1) * 100, 2),
        "rel_volume": round(rel_vol, 2),
        "pct_below_52w_high": round(pct_below_52w, 2),
        "invalidation_close_below": round(level, 2),
        "recent_low_20d": round(float(low[-20:].min()), 2),
    }


def breakouts(
    bars: dict[str, pd.DataFrame],
    universe: dict[str, UniverseEntry],
    params: BreakoutParams = BreakoutParams(),
) -> list[dict]:
    rows = []
    for symbol, df in bars.items():
        row = _breakout_row(symbol, df, params)
        if row:
            entry = universe.get(symbol)
            row["name"] = entry.name if entry else symbol
            row["industry"] = entry.industry if entry else None
            rows.append(row)
    rows.sort(key=lambda r: -r["rel_volume"])
    return rows


def explain_stock(
    symbol: str,
    bars: dict[str, pd.DataFrame],
    bench: pd.DataFrame,
    universe: dict[str, UniverseEntry],
    rs: RSParams = RSParams(),
    bo: BreakoutParams = BreakoutParams(),
) -> dict | None:
    """Plain-language reasons to watch a stock plus conditions that invalidate the setup.

    All numbers come from stored bars. This is a description of today's data
    and the levels that would contradict it, not a forecast.
    """
    df = bars.get(symbol)
    if df is None:
        return None
    rs_rows = {r["symbol"]: r for r in relative_strength(bars, bench, universe, rs)}
    row = rs_rows.get(symbol)
    close = _closes(df)
    if len(close) < 60:
        return None
    last = float(close.iloc[-1])
    sma50 = float(close.tail(50).mean())
    low20 = float(df["low"].astype(float).tail(20).min())
    reasons: list[str] = []
    invalidations: list[dict] = []
    if row:
        reasons.append(
            f"RS rating {row['rs_rating']}/99: blended excess return vs NIFTY 50 is "
            f"{row['excess_return_pct']:+.1f}% (windows {', '.join(f'{w}d' for w, _ in rs.windows)})."
        )
    bo_row = _breakout_row(symbol, df, bo)
    if bo_row:
        reasons.append(
            f"Closed {bo_row['pct_above_level']:.1f}% above its prior {bo.lookback_days}-day high "
            f"({bo_row['breakout_level']}) on {bo_row['rel_volume']}x average volume."
        )
        invalidations.append(
            {"rule": f"Close back below the {bo.lookback_days}-day breakout level", "level": bo_row["breakout_level"]}
        )
    if last > sma50:
        reasons.append(f"Trading above its 50-day average ({sma50:.2f}).")
    invalidations.append({"rule": "Close below the 50-day average", "level": round(sma50, 2)})
    invalidations.append({"rule": "Close below the lowest low of the last 20 sessions", "level": round(low20, 2)})
    if row and row["rs_rating"] < 50:
        reasons.append("Relative strength is below the median of the universe, so no strength case today.")
    entry = universe.get(symbol)
    return {
        "symbol": symbol,
        "name": entry.name if entry else symbol,
        "industry": entry.industry if entry else None,
        "last_close": round(last, 2),
        "as_of": str(df["date"].iloc[-1])[:10],
        "rs_rating": row["rs_rating"] if row else None,
        "reasons": reasons,
        "invalidations": invalidations,
        "note": "Descriptive, from delayed daily bars. Not a prediction or advice.",
    }


# ---- rule backtester (fixed menu, no user code) -----------------------------

ENTRY_RULES = {"breakout", "sma_cross", "momentum"}
EXIT_RULES = {"below_sma", "trailing_stop", "hold_days"}


@dataclass(frozen=True)
class RuleSpec:
    entry: str = "breakout"
    entry_n: int = 55            # breakout lookback / momentum lookback / slow SMA
    entry_fast: int = 20         # fast SMA for sma_cross
    entry_threshold_pct: float = 10.0  # momentum: N-day return above this
    exit: str = "below_sma"
    exit_n: int = 20             # SMA length / hold days
    exit_stop_pct: float = 10.0  # trailing stop percent
    cost_bps: float = 10.0       # fees per side, applied on each position change
    slippage_bps: float = 10.0   # assumed adverse fill per side, same mechanics as fees

    def validate(self) -> None:
        if self.entry not in ENTRY_RULES or self.exit not in EXIT_RULES:
            raise ValueError("Unknown rule")
        for v in (self.entry_n, self.entry_fast, self.exit_n):
            if not 2 <= v <= 400:
                raise ValueError("Lookbacks must be between 2 and 400 days")
        if not 0 <= self.cost_bps <= 500 or not 0 <= self.slippage_bps <= 500:
            raise ValueError("Costs and slippage must be between 0 and 500 bps per side")
        if not 0.5 <= self.exit_stop_pct <= 50:
            raise ValueError("Stop must be between 0.5% and 50%")


def _entry_signal(df: pd.DataFrame, r: RuleSpec) -> pd.Series:
    close = df["close"].astype(float)
    if r.entry == "breakout":
        prior_high = df["high"].astype(float).shift(1).rolling(r.entry_n).max()
        return close > prior_high
    if r.entry == "sma_cross":
        return close.rolling(r.entry_fast).mean() > close.rolling(r.entry_n).mean()
    return close.pct_change(r.entry_n) * 100 > r.entry_threshold_pct


def _max_dd(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1).min() * 100) if len(equity) else 0.0


def _stats(daily: np.ndarray) -> dict:
    if len(daily) == 0:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "days": 0}
    equity = np.cumprod(1 + daily)
    return {
        "return_pct": round(float((equity[-1] - 1) * 100), 2),
        "max_drawdown_pct": round(_max_dd(equity), 2),
        "days": int(len(daily)),
    }


def backtest_rule(df: pd.DataFrame, bench: pd.DataFrame, rule: RuleSpec, oos_fraction: float = 0.3) -> dict:
    """Long-only, one position at a time. Signals use the close; the position is
    held from the *next* bar, so there is no same-bar lookahead. Costs are charged
    on every entry and exit. The last ``oos_fraction`` of bars is reported separately.
    """
    rule.validate()
    df = df.reset_index(drop=True)
    if len(df) < max(rule.entry_n, rule.exit_n, 60) + 60:
        raise ValueError("Not enough history for this rule")
    close = df["close"].astype(float).to_numpy()
    rets = np.diff(close) / close[:-1]
    entry = _entry_signal(df, rule).fillna(False).to_numpy()
    sma_exit = df["close"].astype(float).rolling(rule.exit_n).mean().to_numpy()

    pos = np.zeros(len(df))  # position held *during* bar i's return (decided at close of i-1)
    in_pos, peak, held, trades = False, 0.0, 0, 0
    for i in range(len(df) - 1):
        if in_pos:
            peak = max(peak, close[i])
            held += 1
            if rule.exit == "below_sma":
                out = close[i] < sma_exit[i]
            elif rule.exit == "trailing_stop":
                out = close[i] <= peak * (1 - rule.exit_stop_pct / 100)
            else:
                out = held >= rule.exit_n
            if out:
                in_pos = False
        elif entry[i]:
            in_pos, peak, held = True, close[i], 0
            trades += 1
        pos[i + 1] = 1.0 if in_pos else 0.0

    cost = (rule.cost_bps + rule.slippage_bps) / 10000
    changes = np.abs(np.diff(pos, prepend=0.0))[1:]
    strat = pos[1:] * rets - changes * cost
    # Benchmark return over the same dates as the stock, aligned by date (not by position).
    joined = pd.DataFrame({"date": pd.to_datetime(df["date"]).dt.date, "stock": close}).merge(
        pd.DataFrame({"date": pd.to_datetime(bench["date"]).dt.date, "bench": bench["close"].astype(float).to_numpy()}),
        on="date",
        how="inner",
    )
    bench_rets = joined["bench"].pct_change().dropna().to_numpy()
    split = int(len(strat) * (1 - oos_fraction))
    bh_oos = rets[split:]
    return {
        "rule": rule.__dict__,
        "trades": trades,
        "time_in_market_pct": round(float(pos[1:].mean() * 100), 1),
        "full": {"strategy": _stats(strat), "buy_and_hold": _stats(rets), "nifty50_buy_and_hold": _stats(bench_rets)},
        "benchmark_days_aligned": int(len(joined)),
        "out_of_sample": {
            "starts": str(df["date"].iloc[split + 1])[:10],
            "strategy": _stats(strat[split:]),
            "buy_and_hold": _stats(bh_oos),
        },
        "equity_curve": [
            {"date": str(df["date"].iloc[i + 1])[:10], "strategy": round(float(s), 4), "buy_and_hold": round(float(b), 4)}
            for i, (s, b) in list(enumerate(zip(np.cumprod(1 + strat), np.cumprod(1 + rets))))[:: max(1, len(strat) // 120)]
        ],
        "assumptions": [
            "Long-only, one position, no leverage or shorting.",
            f"Fees of {rule.cost_bps:g} bps plus a flat slippage assumption of {rule.slippage_bps:g} bps charged per entry and per exit (not a market-impact model).",
            "Signals use the close and the position starts the next trading day.",
            "Tested on today's Nifty 500 constituents only (survivorship bias): stocks that left the index are absent.",
            "The out-of-sample period is only a holdout: rules you pick or change after seeing it make it in-sample in practice. Treat it as a sanity check, not validated performance.",
            "Past results do not indicate future results.",
        ],
    }


def breadth(bars: dict[str, pd.DataFrame]) -> dict:
    """Market breadth across the loaded universe: how many stocks are above their
    50/200-day averages and how many sit at 52-week highs vs lows."""
    above50 = above200 = n50 = n200 = highs = lows = n52 = 0
    for df in bars.values():
        close = df["close"].astype(float)
        last = float(close.iloc[-1])
        if len(close) >= 50:
            n50 += 1
            above50 += last > float(close.tail(50).mean())
        if len(close) >= 200:
            n200 += 1
            above200 += last > float(close.tail(200).mean())
        if len(close) >= 252:
            n52 += 1
            highs += last >= float(df["high"].astype(float).tail(252).max()) * 0.98
            lows += last <= float(df["low"].astype(float).tail(252).min()) * 1.02

    def pct(a: int, b: int) -> float | None:
        return round(a / b * 100, 1) if b else None

    return {
        "pct_above_50dma": pct(above50, n50),
        "pct_above_200dma": pct(above200, n200),
        "near_52w_high": highs,
        "near_52w_low": lows,
        "counted_52w": n52,
        "definition": "Near 52-week high/low = within 2% of the 252-session high/low.",
    }


def changes(
    bars: dict[str, pd.DataFrame],
    bench: pd.DataFrame,
    universe: dict[str, UniverseEntry],
    rs: RSParams = RSParams(),
    bo: BreakoutParams = BreakoutParams(),
    top: int = 15,
    recent_days: int = 10,
) -> dict:
    """What changed since the previous session, from stored bars only."""
    now = {r["symbol"]: r for r in relative_strength(bars, bench, universe, rs, 0)}
    before = {r["symbol"]: r for r in relative_strength(bars, bench, universe, rs, 1)}
    moves = []
    for sym, r in now.items():
        prev = before.get(sym)
        if prev:
            moves.append({"symbol": sym, "name": r["name"], "rs_now": r["rs_rating"], "rs_before": prev["rs_rating"], "change": r["rs_rating"] - prev["rs_rating"]})
    moves.sort(key=lambda m: m["change"])
    prev_bars = {k: v.iloc[:-1] for k, v in bars.items() if len(v) > 1}
    today = {r["symbol"] for r in breakouts(bars, universe, bo)}
    yesterday = {r["symbol"] for r in breakouts(prev_bars, universe, bo)}
    broken = []
    for sym, df in bars.items():
        close = df["close"].astype(float).to_numpy()
        for k in range(1, recent_days + 1):  # breakout k sessions ago, now back below its level
            window = df.iloc[: len(df) - k]
            row = _breakout_row(sym, window, bo)
            if row:
                if close[-1] < row["breakout_level"]:
                    entry = universe.get(sym)
                    broken.append({"symbol": sym, "name": entry.name if entry else sym, "breakout_sessions_ago": k,
                                   "level": row["breakout_level"], "close": round(float(close[-1]), 2)})
                break
    return {
        "rs_weakened": moves[:top],
        "rs_strengthened": list(reversed(moves[-top:])),
        "new_breakouts": sorted(today - yesterday),
        "breakout_levels_lost": broken[:top],
        "note": f"Compares the latest session with the one before it; levels lost looks back {recent_days} sessions.",
    }


def raw_snapshot(df: pd.DataFrame, bench: pd.DataFrame, rs: RSParams, bo: BreakoutParams) -> dict:
    """Raw values needed to recompute a signal without the later data: last bar, lagged closes, breakout window."""
    c, b = _closes(df), _closes(bench)
    snap: dict = {"source": DATA_SOURCE, "formula_version": FORMULA_VERSION, "bar_date": str(df["date"].iloc[-1])[:10],
                  "close": float(c.iloc[-1]), "benchmark_close": float(b.iloc[-1]), "closes_lagged": {}, "benchmark_closes_lagged": {}}
    for w, _ in rs.windows:
        if len(c) > w and len(b) > w:
            snap["closes_lagged"][str(w)] = float(c.iloc[-1 - w])
            snap["benchmark_closes_lagged"][str(w)] = float(b.iloc[-1 - w])
    n = bo.lookback_days
    if len(df) > n:
        snap["prior_high_window"] = {"days": n, "high": float(df["close"].iloc[-1 - n:-1].max())}
    v = df["volume"].astype(float)
    if len(v) > 20:
        snap["volume"] = {"last": float(v.iloc[-1]), "avg_prior_20d": float(v.iloc[-21:-1].mean())}
    return snap


def current_signals(
    bars: dict[str, pd.DataFrame],
    bench: pd.DataFrame,
    universe: dict[str, UniverseEntry],
    rs: RSParams = RSParams(),
    bo: BreakoutParams = BreakoutParams(),
) -> list[dict]:
    """Signals observed in the latest session: breakouts, and RS 90+ (top decile)."""
    as_of = str(bench["date"].iloc[-1])[:10]
    out = [
        {"date": as_of, "symbol": r["symbol"], "kind": "breakout", "close": r["close"],
         "inputs": {**{k: r[k] for k in ("breakout_level", "pct_above_level", "rel_volume", "pct_below_52w_high")}, "raw": raw_snapshot(bars[r["symbol"]], bench, rs, bo)}}
        for r in breakouts(bars, universe, bo)
    ]
    out += [
        {"date": as_of, "symbol": r["symbol"], "kind": "rs_top_decile", "close": float(bars[r["symbol"]]["close"].iloc[-1]),
         "inputs": {"rs_rating": r["rs_rating"], "excess_return_pct": r["excess_return_pct"], "returns_pct": r["returns_pct"], "raw": raw_snapshot(bars[r["symbol"]], bench, rs, bo)}}
        for r in relative_strength(bars, bench, universe, rs) if r["rs_rating"] >= 90
    ]
    return out


def score_signal(sig_date: str, symbol_bars: pd.DataFrame, bench: pd.DataFrame, horizons=(5, 20, 60), entry_floor: str | None = None) -> dict:
    """Forward return of a logged signal vs NIFTY 50, N trading days after entry.

    The signal is known only after the source bar closes, so entry is the NEXT
    session's close and the horizons count from there. Pending until enough bars exist.
    """
    d = pd.to_datetime(sig_date).date()
    sd = pd.to_datetime(symbol_bars["date"]).dt.date.reset_index(drop=True)
    bd = pd.to_datetime(bench["date"]).dt.date.reset_index(drop=True)
    si, bi = sd.index[sd == d], bd.index[bd == d]
    if entry_floor:  # entry = first session on/after the floor (strictly after the observation)
        f = pd.to_datetime(entry_floor).date()
        si, bi = sd.index[sd >= f][:1], bd.index[bd >= f][:1]
        si, bi = (si - 1), (bi - 1)  # code below adds 1 for entry
        if len(si) == 0 or len(bi) == 0 or si[0] < 0 or bi[0] < 0:
            return {f"d{h}": None for h in horizons}
    result: dict = {}
    for h in horizons:
        key = f"d{h}"
        if len(si) == 0 or len(bi) == 0:
            result[key] = None
            continue
        s0, b0 = si[0] + 1, bi[0] + 1  # entry: next session's close
        if s0 + h >= len(sd) or b0 + h >= len(bd) or sd.iloc[s0] != bd.iloc[b0]:
            result[key] = None
            continue
        sr = float(symbol_bars["close"].iloc[s0 + h] / symbol_bars["close"].iloc[s0] - 1)
        br = float(bench["close"].iloc[b0 + h] / bench["close"].iloc[b0] - 1)
        result[key] = {"return_pct": round(sr * 100, 2), "vs_nifty_pct": round((sr - br) * 100, 2)}
    return result
