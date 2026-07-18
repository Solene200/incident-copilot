FROM ghcr.io/astral-sh/uv:0.11.29-python3.13-trixie-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --extra demo --extra postgres

COPY data ./data
COPY scripts ./scripts

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "incident_copilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
