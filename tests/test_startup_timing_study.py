"""Local timing study only. No app configuration/estimator changes are shipped."""

import json
import time
import resource
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits
from app import demo
from app.core.config import settings
from app.market_data.base import MarketBar
from app.services.features import build_training_frame, FEATURE_COLUMNS
from app.services.training import train_model


def test_offline_sixteen_symbol_and_sample_cold_warm_timing(session_factory, monkeypatch, tmp_path):
    raw = pd.read_csv("data/sample_prices.csv")
    symbols = [f"FIXTURE{i:02d}" for i in range(16)]
    monkeypatch.setattr(settings, "market_data_symbols", ",".join(symbols))
    monkeypatch.setattr(settings, "nse_symbols", "")
    monkeypatch.setattr(settings, "demo_seed_max_symbols", 20)

    class Provider:
        name = "offline-csv-timing-fixture"

        def history(self, symbol, limit):
            return [
                MarketBar(
                    date=str(r["date"]),
                    symbol=symbol,
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=int(r["volume"]),
                )
                for r in raw.tail(limit).to_dict("records")
            ]

    monkeypatch.setattr(demo, "get_provider_for_symbol", lambda _: Provider())
    frame = build_training_frame(raw)
    baseline = None
    records = []
    from sklearn.ensemble import RandomForestRegressor as RF
    import app.services.training as training
    import app.services.walk_forward as walk

    for mode in ("current", "single"):

        def forest(**kwargs):
            if mode == "single":
                kwargs["n_jobs"] = 1
            return RF(**kwargs)

        monkeypatch.setattr(demo, "RandomForestRegressor", forest)
        monkeypatch.setattr(training, "RandomForestRegressor", forest)
        monkeypatch.setattr(walk, "RandomForestRegressor", forest)
        for repeat in range(2):
            out = tmp_path / (mode + str(repeat))
            out.mkdir()
            monkeypatch.setattr(demo, "MODELS_DIR", out)
            session = session_factory()
            # Native thread cap is part of single hypothesis only.
            with threadpool_limits(limits=1 if mode == "single" else None):
                start = time.perf_counter()
                ingested = demo._ingest_live_symbols(session)
                ingest = time.perf_counter() - start
                start = time.perf_counter()
                trained = demo._train_live_symbol_models(session)
                live = time.perf_counter() - start
                assert trained == 16
                predictions = np.array(
                    [
                        joblib.load(out / f"stocksense_rf_{s}.joblib").predict(
                            frame[FEATURE_COLUMNS]
                        )
                        for s in symbols
                    ]
                )
                if baseline is None:
                    baseline = predictions
                else:
                    np.testing.assert_allclose(predictions, baseline, rtol=1e-12, atol=1e-12)
                start = time.perf_counter()
                warm = demo._train_live_symbol_models(session)
                warmtime = time.perf_counter() - start
                assert warm == 0
                start = time.perf_counter()
                train_model(
                    model_path=str(out / "sample.joblib"),
                    registry_path=str(out / "registry.json"),
                    metrics_path=str(out / "metrics.json"),
                    predictions_path=str(out / "evaluation.csv"),
                )
                sample = time.perf_counter() - start
            session.close()
            records.append(
                {
                    "mode": mode,
                    "repeat": repeat,
                    "rows_per_symbol": len(raw),
                    "symbols": 16,
                    "ingested_rows": ingested,
                    "ingest_fixture_seconds": round(ingest, 4),
                    "live_fit_write_seconds": round(live, 4),
                    "warm_existing_models_seconds": round(warmtime, 4),
                    "sample_evaluate_fit_write_seconds": round(sample, 4),
                    "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "predictions_equal_1e12": True,
                }
            )
    print("TIMING_STUDY=" + json.dumps(records), flush=True)
