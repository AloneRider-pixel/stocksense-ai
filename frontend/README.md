# StockSense AI Web

React dashboard for the StockSense AI API.

## Scope

- Authentication.
- Prediction execution.
- Per-user prediction history.
- Evaluation/result views.

The frontend is a thin client: market-data provider credentials, model execution, and scoring remain server-side.

## Local development

From repository root:

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the API is not on localhost.

## Verification

```bash
npm run build
```

Repository CI additionally runs backend lint/tests and the reproducible sample-data evaluation.

## Security

Do not put provider or database credentials in browser configuration. Keep user-scoped data authorization on the backend and validate API errors/empty states in UI flows.

## Review path

Review `src/lib/api.js`, authentication flows, and data rendering when API contracts change.
