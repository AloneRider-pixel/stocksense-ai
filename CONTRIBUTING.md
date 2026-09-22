# Contributing

## Development flow

1. Create a branch from `main`.
2. Make one focused change.
3. Run the local quality gates:
   `make lint`
   `make test`
   `make build-frontend`
4. Update tests and documentation when behavior changes.
5. Open a pull request with a concise problem statement, implementation summary, and validation notes.

## Engineering expectations

- Preserve the API boundaries between routes, services, repositories, and providers.
- Do not commit secrets, credentials, generated model artifacts, or local environment files.
- Keep time-series evaluation free from future-data leakage.
- Prefer deterministic, reproducible tests for provider and repository behavior.
- Use migrations for database schema changes.

## Pull requests

A good pull request should explain:

- What changed and why.
- How the change was tested.
- Any operational or migration impact.
- Any follow-up work that remains.

See `.github/pull_request_template.md` for the review checklist.
