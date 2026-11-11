.PHONY: up down logs seed db api web migrate test lint check

# --- Full stack in Docker (http://localhost:8080) ---
up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api web

seed:
	docker compose exec api python -m app.seed

# --- Local development (API :8000, web :5173 with hot reload) ---
db:
	docker compose up -d db

migrate:
	cd apps/api && uv run alembic upgrade head

api: migrate
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

# --- Quality gates (needs `make db` running for API tests) ---
test:
	cd apps/api && uv run pytest
	cd apps/web && npm test

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && npm run lint && npm run typecheck

check: lint test
	cd apps/web && npm run build
