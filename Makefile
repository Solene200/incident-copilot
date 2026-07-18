.PHONY: sync format format-check lint typecheck test run rag-ingest rag-search graph-demo graph-mermaid demo-observability demo-down

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

demo-observability:
	docker compose --profile demo up --build --abort-on-container-exit --exit-code-from demo demo

demo-down:
	docker compose --profile demo down -v --remove-orphans

run:
	uv run uvicorn incident_copilot.main:app --reload

rag-ingest:
	uv run python scripts/ingest_knowledge.py

rag-search:
	uv run python scripts/search_knowledge.py --query "database connection pool timeout" --service payment-service

graph-demo:
	uv run python scripts/run_investigation.py

graph-mermaid:
	uv run python scripts/render_graph.py --check docs/GRAPH_CURRENT.md
