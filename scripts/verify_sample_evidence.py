"""Verify the provenance and consistency of the reproducible sample-data evaluation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "sample_prices.csv"
METRICS = ROOT / "models" / "metrics.json"
REGISTRY = ROOT / "models" / "registry.json"
PREDICTIONS = ROOT / "models" / "walk_forward_predictions.csv"
EVIDENCE = ROOT / "models" / "evidence_verification.json"


def canonical_data_sha() -> str:
    frame = pd.read_csv(DATA)
    canonical = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    return hashlib.sha256(canonical.to_csv(index=False).encode("utf-8")).hexdigest()


metrics = json.loads(METRICS.read_text(encoding="utf-8"))
registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
rows = list(csv.DictReader(PREDICTIONS.open(encoding="utf-8")))

required_metrics = {
    "data_sha256",
    "folds",
    "test_rows",
    "mae",
    "rmse",
    "mape_pct",
    "directional_accuracy_pct",
    "baseline_mae",
    "improvement_vs_last_close_pct",
}
missing = required_metrics - metrics.keys()
if missing:
    raise SystemExit(f"Missing evaluation metrics: {', '.join(sorted(missing))}")

if metrics["data_sha256"] != canonical_data_sha():
    raise SystemExit("Evaluation data hash does not match the checked-in sample dataset.")
if not isinstance(metrics["folds"], int) or metrics["folds"] < 2:
    raise SystemExit("Evaluation must use at least two time-series folds.")
if metrics["test_rows"] != len(rows) or metrics["test_rows"] <= 0:
    raise SystemExit("Evaluation test-row count does not match the prediction artifact.")

for key in ("mae", "rmse", "mape_pct", "baseline_mae", "improvement_vs_last_close_pct"):
    value = float(metrics[key])
    if not math.isfinite(value):
        raise SystemExit(f"Metric {key} is not finite.")
directional = float(metrics["directional_accuracy_pct"])
if not 0 <= directional <= 100:
    raise SystemExit("Directional accuracy must be between 0 and 100.")

for row in rows:
    if row["prediction_date"] <= row["train_end_date"]:
        raise SystemExit(
            f"Future-leakage check failed: {row['prediction_date']} <= {row['train_end_date']}"
        )

registry_features = registry.get("features")
if not registry.get("version") or not registry_features:
    raise SystemExit("Model registry is missing version or feature metadata.")
if registry.get("dataset") != f"csv:{DATA.relative_to(ROOT)}":
    raise SystemExit("Model registry dataset source does not identify the checked-in fixture.")

evidence = {
    "evaluation": "sample-data-walk-forward",
    "dataset_sha256": metrics["data_sha256"],
    "folds": metrics["folds"],
    "test_rows": metrics["test_rows"],
    "directional_accuracy_pct": directional,
    "baseline_mae": float(metrics["baseline_mae"]),
    "improvement_vs_last_close_pct": float(metrics["improvement_vs_last_close_pct"]),
    "prediction_rows_verified": len(rows),
    "future_leakage_check": "passed",
    "registry_version": registry["version"],
}
EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(
    "sample evaluation evidence verified: "
    f"rows={len(rows)}, folds={metrics['folds']}, data_sha256={metrics['data_sha256']}"
)
