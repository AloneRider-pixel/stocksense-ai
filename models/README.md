# StockSense AI Model Artifacts

The `models/` directory is an artifact boundary for generated model and evaluation outputs. Generated artifacts are runtime/evaluation evidence, not authoritative application source.

## Expected artifacts

Depending on the workflow, generated outputs may include:

- serialized model artifacts;
- evaluation metrics;
- registry metadata; and
- row-level walk-forward predictions.

## Artifact provenance

A promoted or published artifact should retain or reference:

| Field | Purpose |
|---|---|
| Model version | Identifies the exact model/configuration |
| Feature set | Defines the input contract |
| Dataset/source | Establishes provenance |
| Cutoff/evaluation period | Preserves temporal validity |
| Method | Explains training/evaluation procedure |
| Metrics | Defines reported results |
| Environment | Captures runtime/toolchain context |
| Producing commit | Makes the artifact traceable to source |

## Integrity rules

- Never commit credentials, raw customer/user data, or sensitive provider data.
- Never treat an artifact without provenance as reproducible evidence.
- Never compare runs without identifying dataset, method, environment, and model version.
- Keep walk-forward predictions aligned with their chronological evaluation window.

See [model evaluation](../docs/model-evaluation.md) and the repository verification workflow.

## License

MIT
