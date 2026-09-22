install:
	python -m pip install -r requirements.txt

test:
	pytest -q

lint:
	ruff check app tests

train:
	python -m app.services.training

train-real:
	python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000

ingest:
	python -m app.market_data.cli --symbol AAPL --limit 500

migrate:
	alembic upgrade head

api:
	uvicorn app.main:app --reload

worker:
	python -m app.workers.worker

frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build

up:
	docker compose up --build
