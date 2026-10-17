"""Phase 3: watchlists and the universe screener."""

from __future__ import annotations

from app.services.screener import screen_universe


def _bars(closes, volume=1000):
    return [
        {"date": f"2026-03-{(i % 28) + 1:02d}", "close": c, "volume": volume}
        for i, c in enumerate(closes)
    ]


def test_screener_computes_real_metrics():
    up = _bars([100 + i for i in range(30)])      # steady climber, RSI 100
    down = _bars([100 - i * 0.5 for i in range(30)])
    out = screen_universe({"RELIANCE": up, "AAPL": down})
    by_symbol = {r["symbol"]: r for r in out}
    assert by_symbol["RELIANCE"]["rsi14"] == 100.0
    assert by_symbol["RELIANCE"]["above_sma20"] is True
    assert by_symbol["AAPL"]["above_sma20"] is False
    assert by_symbol["RELIANCE"]["currency"] == "INR"
    assert by_symbol["AAPL"]["change_pct"] < 0


def test_screener_skips_short_history():
    out = screen_universe({"RELIANCE": _bars([100 + i for i in range(10)])})
    assert out == []


def test_screener_filters():
    up = _bars([100 + i for i in range(30)])
    down = _bars([100 - i * 0.5 for i in range(30)])
    histories = {"RELIANCE": up, "AAPL": down}

    assert [r["symbol"] for r in screen_universe(histories, exchange="NSE")] == ["RELIANCE"]
    assert [r["symbol"] for r in screen_universe(histories, min_change_pct=0)] == ["RELIANCE"]
    assert [r["symbol"] for r in screen_universe(histories, max_rsi=50)] == ["AAPL"]
    assert [r["symbol"] for r in screen_universe(histories, above_sma20=True)] == ["RELIANCE"]
    assert screen_universe(histories, min_volume=5000) == []


def test_watchlist_crud(client, auth_headers):
    headers, _ = auth_headers

    response = client.get("/api/v1/watchlist", headers=headers)
    assert response.status_code == 200
    assert response.json()["symbols"] == []

    added = client.post("/api/v1/watchlist", json={"symbol": "reliance"}, headers=headers)
    assert added.status_code == 201
    assert added.json()["symbols"] == ["RELIANCE"]

    # Idempotent: adding again does not duplicate.
    again = client.post("/api/v1/watchlist", json={"symbol": "RELIANCE"}, headers=headers)
    assert again.status_code == 201
    assert again.json()["added"] is False
    assert again.json()["symbols"] == ["RELIANCE"]

    # Unknown symbol rejected with a clear reason.
    bad = client.post("/api/v1/watchlist", json={"symbol": "NOTREAL"}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "SYMBOL_NOT_SUPPORTED"

    removed = client.delete("/api/v1/watchlist/RELIANCE", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["symbols"] == []

    missing = client.delete("/api/v1/watchlist/RELIANCE", headers=headers)
    assert missing.status_code == 404


def test_screener_endpoint(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr("app.core.config.settings.market_data_provider", "csv")
    monkeypatch.setattr("app.core.config.settings.market_data_symbols", "DEMO")
    monkeypatch.setattr("app.core.config.settings.nse_symbols", "")

    ingest = client.get("/api/v1/stocks/DEMO/history?limit=100", headers=headers)
    assert ingest.status_code == 200

    response = client.get("/api/v1/screener", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["universe"] == 1
    assert payload["scanned"] == 1
    assert len(payload["results"]) == 1
    row = payload["results"][0]
    assert row["symbol"] == "DEMO"
    assert row["rsi14"] is not None
    assert "delayed" in payload["disclaimer"]
