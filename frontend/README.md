# StockSense AI Web

React client for the StockSense AI API.

## Scope

The frontend owns presentation and interaction only:

- authentication UI;
- prediction requests and result rendering;
- user-scoped prediction history;
- evaluation and reconciliation views; and
- API loading/error states.

Model execution, provider credentials, authorization, and persistence remain server-side.

## Development

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the API is hosted somewhere other than the expected local endpoint.

## Verification

```bash
npm run build
```

For full-stack contract changes, also run the backend tests and evidence verification from the repository root.

## Security

Never expose database credentials, model/provider keys, or server-only configuration through `VITE_*` variables. Treat API errors as distinct from empty data and keep authorization on the backend.

## Review path

For API-contract changes, review `src/lib/api.js`, authentication flows, prediction rendering, loading/error states, and evaluation result presentation together.

## License

MIT
