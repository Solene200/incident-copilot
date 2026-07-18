.PHONY: sync format format-check lint typecheck test run rag-ingest rag-search

sync:
	uv sync

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run mypy src tests

test:
	uv run pytest

run:
	uv run uvicorn incident_copilot.main:app --reload

rag-ingest:
	uv run python scripts/ingest_knowledge.py

rag-search:
	uv run python scripts/search_knowledge.py --query "database connection pool timeout" --service payment-service
