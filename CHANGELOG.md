# Changelog

All notable changes to StockSense AI. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-10-22

First tagged release: an India-first model-evaluation sandbox with a live,
publicly scored track record.

### Added

- India-first universe: full NIFTY 50 constituents (NSE via Yahoo Finance),
  the NIFTY 50 index as benchmark, spot gold/silver, and USD/INR, EUR/INR,
  GBP/INR pairs. INR, Asia/Kolkata, NSE 2026 holiday calendar. (#45, #65)
- Public track record: every served forecast is stored and reconciled against
  the next real close; `/public/accuracy` compares the model against
  last-close persistence and the NIFTY 50 index over the same windows.
  Sample sizes shown on purpose. (#58, #63, #65)
- Walk-forward backtest view: long/flat strategy vs buy-and-hold, equity
  curve and max drawdown, assumptions disclosed. (#58)
- Watchlists and a universe screener. (#47)
- Public demo site: landing page with live market snapshot and track record,
  one-click demo sign-in, dashboard with candlesticks + indicators,
  predicted-vs-actual chart, accuracy by symbol. (#43, #58)
- Structured JSON request logging with request IDs (`LOG_LEVEL`,
  `LOG_FORMAT`); `X-Request-ID` response header for correlation. (#66)
- Twelve Data -> Yahoo Finance fallback chain for metals and FX. (#67)
- Coverage measurement in CI with a published badge and an 85% floor. (#64)
- API endpoint guide with real request/response examples. (#62)
- SEBI-conservative framing throughout: evaluation-sandbox language,
  no buy/sell/target wording, README Limitations and Regulatory note. (#65)

### Fixed

- Model trains on return ratios so live predictions stay in range. (#44)
- Panel-feature leakage in training data. (#40)
- Naive-datetime handling in stored stock history. (#39)

### Infrastructure

- Demo API database moved to a persistent managed Postgres (Neon) so the
  track record survives redeploys; previously SQLite on ephemeral storage
  wiped it on every deploy.
- Auto-deploy enabled on both Render services.
