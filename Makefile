install:
	python -m pip install -r requirements.txt

test:
	pytest -q

lint:
	ruff check app tests

train:
	python -m app.services.training

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
