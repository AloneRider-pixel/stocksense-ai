# Nifty 500 scanner

Descriptive tools over delayed daily bars. Not investment advice, not a prediction, and not a SEBI-registered research analyst service.

## Data
- Universe: NSE Indices' public Nifty 500 constituent list, downloaded on demand to `data/nifty500_constituents.csv` (git-ignored on purpose: redistribution terms are unverified, so the file is not committed). `python -m app.market_data.scanner_ingest --fetch-universe` fetches it. The file's column is NSE's *Industry* classification and is shown as "industry".
- Prices: Yahoo Finance via the unofficial `yfinance` client, stored in `scanner_bars`. Load with `python -m app.market_data.scanner_ingest`. The in-app "Refresh data" button is off unless `SCANNER_REFRESH_ENABLED=true`, runs one load at a time with a cooldown (`SCANNER_REFRESH_COOLDOWN_MINUTES`, default 360), and requires sign-in.
- Licensing: neither source was confirmed as licensed for redistribution. Treat as a personal/demo research tool until that is checked. Do not publish scan output as a product.

## Formulas (StockSense's own, not a standard)
- RS rating: weighted excess return vs NIFTY 50 over 63/126/252 trading days (weights 0.4/0.3/0.3), percentile-ranked 1-99 among ranked stocks.
- Industry rotation: median RS of an industry now vs 20 trading days earlier (industries with fewer than 3 ranked stocks omitted).
- Breakout: latest close above the highest high of the prior N sessions (default 55), volume at least 1.5x the prior 20-session average.
- Explain panel: the exact inputs behind a stock's appearance plus levels that would contradict the setup (breakout level, 50-day average, 20-session low).
- Rule backtest: fixed menu of rules, long-only, signal on close and position from the next day, fees plus slippage per side, last 30% reported out-of-sample, compared with buy-and-hold and NIFTY 50. Current constituents only (survivorship bias).

## Data quality gate
Before ranking, a series is excluded (and counted on the page) if: its last bar is older than the benchmark's, prices are non-positive or inconsistent, more than 5 benchmark sessions are missing inside its own date range, or it has a one-day move over 25% in the last 252 sessions (possible unadjusted split/demerger; a genuine move is excluded too, which is the safe side). Provider prices are split-adjusted by Yahoo but not guaranteed correct.

## What changed and the signal scorecard
- "What changed" is computed from stored bars: RS rating change vs the previous session, breakouts new today, breakout levels lost in the last 10 sessions.
- The scorecard is signed-in only; nothing is published. Each live refresh stores an immutable run (observed time UTC, bar date, rules version, config, data exclusions) and its signals with an inputs snapshot of raw values (last close, lagged closes for each RS window, benchmark closes, prior 55-day high, volume and 20-day average, data source, formula version). A run is *forward* only if it was live and its bar date was the latest completed session at observation time (IST, bars treated as final after 16:00). Entry is the close of the first weekday session strictly after the observation date, so a run observed after the entry session can never be forward. Imported, backfilled, recomputed, delayed (multi-day outage) or stale-bar runs are *retrospective* and kept out of the headline. Exchange holidays are not modelled: a run after a holiday may be labelled retrospective (safe direction). Horizons are 5/20/60 trading days from entry vs NIFTY 50. Rows are only inserted. If rules change (`FORMULA_VERSION`), older rows are labelled superseded, never rewritten.

## Price adjustments (what is and is not verified)
Prices are requested with `auto_adjust=False`, which yfinance documents as Yahoo's split-adjusted OHLC plus a separate `Adj Close` for dividends (https://ranaroussi.github.io/yfinance/advanced/price_adjustment.html). So returns here exclude dividends. Whether Yahoo also split-adjusts volume was not verified; a split inside the 20-day window could distort the volume ratio. The 25% filter is a data-sanity guardrail, not corporate-action validation: it can exclude genuine jumps and miss smaller unadjusted events.

## Release gates
All `/scanner/*` endpoints return 403 unless `SCANNER_ENABLED=true`, and the data refresh additionally needs `SCANNER_REFRESH_ENABLED=true`. Neither universe nor prices are fetched automatically: use the CLI (`--fetch-universe` for the NSE list). Keep both flags off in any deployment until the Yahoo and NSE data terms are checked.

## Data-quality findings (checked against news, Oct 2026)

The 25% one-day filter excluded four symbols as of 2026-10-23. Checked reasons: VEDL (-64.9% on 2026-04-30) is the Vedanta demerger ex-date, a corporate action not adjusted in the price series; TRENT (-33% on 2026-01-01) matches a bonus-issue price adjustment reported by ET; POLICYBZR (-36% on 2026-09-24) is a real crash on IRDAI proposals, so the filter also excludes genuine moves; HEGAM (-62.6% on 2026-09-07) is probably a demerger-related event but this is unverified. The filter is a guardrail, not corporate-action validation: events under 25% can pass unadjusted.
