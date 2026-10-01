# StockSense AI Web

React client for the StockSense AI API.

## Responsibilities

- Authentication UI.
- Prediction requests and result presentation.
- User-scoped prediction history.
- Evaluation and reconciliation views.

The frontend is intentionally a thin client. Model execution, provider credentials, authorization, and persistence stay on the server.

## Development

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Configure `VITE_API_BASE_URL` when the API is hosted somewhere other than the expected local endpoint.

## Verification

```bash
npm run build
```

Run backend tests and evidence verification from the repository root for full-stack contract changes.

## Security

Never expose database credentials, model/provider keys, or server-only configuration through `VITE_*` variables. Treat API errors and empty states as first-class UI states and keep authorization on the backend.

## Review path

Start with `src/lib/api.js`, authentication flows, prediction rendering, and error handling when API contracts change.

## License

MIT
