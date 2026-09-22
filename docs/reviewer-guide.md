# Reviewer Guide

A fast technical review can follow this sequence:

1. Read `README.md` for the product and runtime boundaries.
2. Read `docs/architecture.md` for persistence, ingestion, prediction, and evaluation flow.
3. Inspect `app/market_data/` to see provider normalization and ingestion boundaries.
4. Inspect `app/services/walk_forward.py` and `app/services/training.py` for time-series evaluation and model lifecycle.
5. Inspect prediction persistence and reconciliation in `app/db/repository.py`.
6. Run the deterministic test suite before using live-provider evaluation.
7. Use `docs/testing.md` and `docs/deployment.md` to distinguish CI evidence from production measurements.

The repository intentionally does not publish unverified uptime or model-performance figures. Any future benchmark should include the dataset source, observation window, baseline, application commit, and generated artifacts.
