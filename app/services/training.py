from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.market_data.factory import get_market_data_provider
from app.services.features import FEATURE_COLUMNS, build_training_frame
from app.services.walk_forward import walk_forward_evaluate, write_walk_forward_artifacts


def load_market_frame(
    *,
    data_path: str | None = None,
    symbol: str | None = None,
    provider_name: str | None = None,
    limit: int = 1000,
) -> tuple[pd.DataFrame, str]:
    if data_path:
        return pd.read_csv(data_path), f"csv:{data_path}"

    if not symbol:
        raise ValueError("Provide either data_path or symbol")

    if provider_name:
        from app.market_data.csv_provider import CSVMarketDataProvider
        from app.market_data.twelve_data import TwelveDataProvider

        if provider_name == "csv":
            provider = CSVMarketDataProvider()
        elif provider_name == "twelve_data":
            provider = TwelveDataProvider()
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
    else:
        provider = get_market_data_provider()

    bars = provider.history(symbol.upper(), limit=limit)
    if not bars:
        raise ValueError(f"No market data returned for symbol {symbol.upper()}")

    return (
        pd.DataFrame([bar.__dict__ for bar in bars]),
        getattr(provider, "name", provider.__class__.__name__),
    )


def train_model(
    data_path: str | None = "data/sample_prices.csv",
    model_path: str = "models/stocksense_rf.joblib",
    metrics_path: str = "models/metrics.json",
    registry_path: str = "models/registry.json",
    predictions_path: str = "models/walk_forward_predictions.csv",
    model_version: str = "random-forest-v0.3",
    symbol: str | None = None,
    provider_name: str | None = None,
    limit: int = 1000,
) -> dict[str, float | int | str]:
    if symbol:
        data_path = None

    raw, source = load_market_frame(
        data_path=data_path,
        symbol=symbol,
        provider_name=provider_name,
        limit=limit,
    )

    frame = build_training_frame(raw)
    if len(frame) < 80:
        raise ValueError("At least 80 usable observations are required")

    evaluation = walk_forward_evaluate(raw, n_splits=5)
    write_walk_forward_artifacts(
        evaluation,
        metrics_path=metrics_path,
        predictions_path=predictions_path,
    )

    final_model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=2,
        n_jobs=-1,
    )
    final_model.fit(frame[FEATURE_COLUMNS], frame["target"])

    registry = {
        "version": model_version,
        "algorithm": "RandomForestRegressor",
        "features": FEATURE_COLUMNS,
        "dataset": source,
        "rows": int(len(frame)),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "evaluation": evaluation.metrics,
    }

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    Path(registry_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, model_path)
    Path(registry_path).write_text(
        json.dumps(registry, indent=2),
        encoding="utf-8",
    )

    metrics = dict(evaluation.metrics)
    metrics["model_version"] = model_version
    metrics["data_source"] = source
    metrics["trained_at"] = registry["trained_at"]

    Path(metrics_path).write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train StockSense AI model.")
    parser.add_argument("--symbol", help="Ticker to retrieve from the configured market-data provider.")
    parser.add_argument("--provider", choices=["twelve_data", "csv"])
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--data-path", default="data/sample_prices.csv")
    parser.add_argument("--model-version", default="random-forest-v0.3")
    args = parser.parse_args()

    result = train_model(
        data_path=args.data_path if not args.symbol else None,
        symbol=args.symbol,
        provider_name=args.provider,
        limit=args.limit,
        model_version=args.model_version,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
