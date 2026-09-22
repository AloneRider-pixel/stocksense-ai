# Security Model

## Authentication

Product endpoints use bearer JWTs issued by the auth service.

## Authorization

Prediction history is filtered by authenticated user ID at the repository boundary. A user therefore cannot request another user's prediction records through the standard API.

## Secrets

Secrets are supplied through environment variables. Development placeholders are intentionally non-production values.

## Abuse controls

Authenticated prediction, history, market-data, and model-metrics endpoints use a Redis fixed-window limiter.

## Application hardening

The HTTP stack adds request IDs and browser-oriented security headers. Pydantic validates inbound payloads before service execution.

## Threat model

The current product foundation is not a financial-trading execution system. Order placement, broker credentials, payment data, and privileged administrative workflows are outside the current API surface.
