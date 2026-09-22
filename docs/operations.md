# Operations Guide

## Local startup

Backend:

    cp .env.example .env
    alembic upgrade head
    python -m app.services.training
    uvicorn app.main:app --reload

Frontend:

    cd frontend
    npm install
    npm run dev

Full stack:

    docker compose up --build

## Health

    GET /api/v1/health

## Runtime metrics

    GET /internal/metrics

## Database migrations

Create and apply schema changes with Alembic:

    alembic upgrade head

Use `Base.metadata.create_all()` only for the local compatibility path. Production schema changes should use Alembic.

## Worker

    python -m app.workers.worker

## Production configuration

Set these environment variables in deployment:

- `JWT_SECRET`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `ALLOWED_HOSTS`

Never commit `.env` files or credentials.
