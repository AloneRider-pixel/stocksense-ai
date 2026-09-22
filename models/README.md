# Model Artifacts

Runtime-generated artifacts are intentionally kept out of source control.

The training service writes:

- stocksense_rf.joblib: serialized model artifact
- metrics.json: evaluation metrics
- registry.json: model version, feature set, dataset, training time, and status

Run:

    python -m app.services.training

The registry format provides a stable boundary for later model promotion and rollback workflows.
