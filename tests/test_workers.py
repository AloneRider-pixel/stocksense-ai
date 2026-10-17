from __future__ import annotations

import asyncio

import pytest
from arq import Retry

import app.workers.tasks as tasks
from app.core.config import settings
from app.market_data.base import MarketBar


class FakeProvider:
    name = "fake"

    def __init__(self, bars=None, error=None):
        self._bars = bars or []
        self._error = error

    def history(self, symbol, limit=100):
        if self._error is not None:
            raise self._error
        return [
            MarketBar(
                date=bar.date,
                symbol=symbol.upper(),
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            for bar in self._bars
        ]


def make_bar(date, close=100.0):
    return MarketBar(
        date=date,
        symbol="DEMO",
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1000,
    )


@pytest.fixture()
def worker_env(monkeypatch, session_factory):
    monkeypatch.setattr(tasks, "get_session", session_factory)
    return session_factory


def test_refresh_market_data_ingests_bars(worker_env, monkeypatch):
    monkeypatch.setattr(
        tasks,
        "get_market_data_provider",
        lambda: FakeProvider([make_bar("2025-01-02"), make_bar("2025-01-03")]),
    )

    result = asyncio.run(tasks.refresh_market_data({"job_try": 1}, "demo"))

    assert result["symbol"] == "DEMO"
    assert result["fetched"] == 2
    assert result["inserted"] == 2
    assert result["predictions_evaluated"] == 0


def test_refresh_market_data_retries_on_failure(worker_env, monkeypatch):
    monkeypatch.setattr(
        tasks,
        "get_market_data_provider",
        lambda: FakeProvider(error=ValueError("provider down")),
    )

    with pytest.raises(Retry):
        asyncio.run(tasks.refresh_market_data({"job_try": 2}, "DEMO"))


def test_refresh_configured_markets_aggregates(worker_env, monkeypatch):
    monkeypatch.setattr(
        tasks,
        "get_market_data_provider",
        lambda: FakeProvider([make_bar("2025-01-02")]),
    )
    monkeypatch.setattr(settings, "market_data_symbols", "DEMO,OTHER")
    monkeypatch.setattr(settings, "nse_symbols", "")

    result = asyncio.run(tasks.refresh_configured_markets({"job_try": 1}))

    assert result == {
        "symbols": 2,
        "fetched": 2,
        "inserted": 2,
        "predictions_evaluated": 0,
    }


def test_worker_settings_registers_tasks():
    from app.workers.worker import WorkerSettings

    assert tasks.refresh_market_data in WorkerSettings.functions
    assert tasks.refresh_configured_markets in WorkerSettings.functions
    assert len(WorkerSettings.cron_jobs) == 1
