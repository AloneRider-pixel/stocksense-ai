# StockSense AI Model Artifacts

The `models/` directory is an artifact boundary for generated model and evaluation outputs. Generated files are runtime evidence, not authoritative source code.

## Expected artifacts

Depending on the workflow, generated outputs may include:

- serialized model artifacts;
- evaluation metrics;
- registry metadata;
- row-level walk-forward predictions.

Each promoted artifact should retain or reference its model version, feature set, dataset/source, cutoff or evaluation period, method, metrics, timestamp, and producing commit.

## Integrity rules

- Do not commit credentials or raw user/customer data.
- Do not treat an artifact without provenance as reproducible evidence.
- Do not compare results across runs without identifying dataset, method, environment, and model version.

See [model evaluation](../docs/model-evaluation.md) and the repository verification workflow.

## License

MIT
