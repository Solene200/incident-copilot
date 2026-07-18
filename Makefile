.PHONY: sync format format-check lint typecheck test run

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

