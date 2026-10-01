# StockSense AI Model Artifacts

This directory documents runtime-generated model/evaluation outputs; generated artifacts are intentionally not treated as source-control truth.

## Generated outputs

- `stocksense_rf.joblib` — serialized model artifact when produced.
- `metrics.json` — evaluation metrics.
- `registry.json` — model version, features, dataset/source, timestamp, and status.
- `walk_forward_predictions.csv` — row-level evaluation predictions in reproducible evaluation runs.

Run training from the repository root with the training module used by the current workflow.

## Artifact integrity

For a promoted model, preserve:

- model version;
- feature set;
- dataset/source and cutoff;
- evaluation method and metrics;
- training timestamp;
- producing commit.

Do not place credentials or raw customer/user data in model bundles.

## Evidence

Generated metrics are meaningful only with their dataset and methodology. The checked-in sample fixture is for reproducibility, not a universal production-performance claim.

## Review path

Start with [model evaluation](../docs/model-evaluation.md) and the repository CI workflow before changing artifact schemas or promotion behavior.
