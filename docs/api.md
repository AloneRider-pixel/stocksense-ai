# StockSense AI API

Base URL (live demo): `https://stocksense-ai-zvo7.onrender.com/api/v1`

Interactive schema (Swagger UI, always generated from the running code): <https://stocksense-ai-zvo7.onrender.com/docs>

Auth: bearer JWT from `POST /auth/login`. Demo credentials: `demo@stocksense.app` / `Demo1234!`.
`/public/*` endpoints need no token. Every response includes a `request_id`; errors use `{"error": {"code", "message", "request_id"}}`.

Examples below are real responses from the live demo (22 Oct 2026), trimmed where marked with `...`.

## 1. Log in - `POST /auth/login`

```bash
curl -X POST https://stocksense-ai-zvo7.onrender.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@stocksense.app","password":"Demo1234!"}'
```

```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 1800}
```

## 2. Daily bars - `GET /stocks/{symbol}/history?limit=12`

```bash
curl 'https://stocksense-ai-zvo7.onrender.com/api/v1/stocks/TCS/history?limit=12' \
  -H "Authorization: Bearer $TOKEN"
```

```json
[{"date": "2026-10-06", "symbol": "TCS", "open": 2085.9111, "high": 2103.8159,
  "low": 2071.6867, "close": 2088.8953, "volume": 2382510, "source_provider": "yfinance_nse"}, ...]
```

NSE bars come from Yahoo Finance, US bars from Twelve Data; `source_provider` says which. Daily bars may be delayed.

## 3. Next-close prediction - `POST /predict`

Send at least 11 recent bars (newest last). The prediction is stored and later scored against the real close.

```bash
curl -X POST https://stocksense-ai-zvo7.onrender.com/api/v1/predict \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"symbol":"TCS","history":[{"date":"2026-10-06","close":2088.8953,"volume":2382510}, ...]}'
```

```json
{"symbol": "TCS", "prediction_date": "2026-10-22", "predicted_close": 2505.5988,
 "expected_change_pct": -0.0519, "model": "random-forest-live-tcs", "cached": false, "persisted": true}
```

`persisted: true` means this forecast entered the scored track record and cannot be edited or deleted.

## 4. Live track record - `GET /public/accuracy` (no auth)

```bash
curl https://stocksense-ai-zvo7.onrender.com/api/v1/public/accuracy
```

```json
{"status": "insufficient_data",
 "overall": {"evaluated_predictions": 0, "mae": null, "directional_accuracy_pct": null,
             "baseline_mae": null, "improvement_vs_persistence_pct": null, ...},
 "symbols": [],
 "benchmark_index": {"symbol": "NIFTY50", "compared_windows": 0, "avg_symbol_return_pct": null, "avg_index_return_pct": null, "share_outperforming_index_pct": null},
    "methodology": "Every forecast served by the API is stored when it is made and reconciled against the next available NSE close. Baselines: last-close persistence and the NIFTY 50 index over the same windows..."}
```

A fresh deployment honestly returns `insufficient_data` until real closes arrive to score against. The model must beat last-close persistence to claim value.

## 5. Walk-forward backtest - `GET /backtest/{symbol}`

```bash
curl https://stocksense-ai-zvo7.onrender.com/api/v1/backtest/TCS \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"symbol": "TCS",
 "metrics": {"evaluation": "walk_forward_long_flat", "periods": 405,
             "strategy_return_pct": -31.3376, "buy_hold_return_pct": -26.6306,
             "strategy_max_drawdown_pct": -40.4348, "buy_hold_max_drawdown_pct": -43.2796,
             "directional_hit_rate_pct": 49.3827},
 "equity_curve": [{"date": "2025-02-25", "strategy": -0.4684, "buy_hold": -0.4684}, ...]}
```

Assumptions: out-of-sample walk-forward, long/flat, no transaction costs, no shorting, no leverage. Illustrative, not investment advice.

## Full endpoint list

Auth: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
Public: `GET /health`, `GET /public/market-overview`, `GET /public/accuracy`, `GET /public/predictions/latest`.
Data: `POST /stocks/{symbol}/ingest`, `GET /stocks/{symbol}/history`, `GET /stocks/{symbol}/indicators`, `GET /symbols`, `GET /screener`.
Model: `POST /predict`, `GET /predictions`, `GET /predictions/evaluation`, `GET /backtest/{symbol}`, `GET /metrics`.
Watchlist: `GET/POST /watchlist`, `DELETE /watchlist/{symbol}`.
