# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability.

Report the issue privately through the security contact configured for the repository and include:

- affected component or endpoint
- reproduction steps
- impact assessment
- relevant logs or request IDs
- suggested mitigation when known

Do not include credentials, API keys, access tokens, or other secrets in reports.

## Security principles

StockSense AI uses:

- password hashing with scrypt
- signed JWT access tokens
- explicit authorization dependencies
- input validation with Pydantic
- parameterized SQLAlchemy queries
- Redis-backed rate limiting
- security response headers
- CI-based testing and dependency controls

Production deployments must provide a strong JWT_SECRET and must not use development credentials.
