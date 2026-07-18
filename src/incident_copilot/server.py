"""Cross-platform Uvicorn entry point with psycopg-compatible Windows asyncio."""

import argparse
import asyncio

import uvicorn


def main() -> None:
    """Run Uvicorn, selecting an event loop supported by async psycopg on Windows."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--log-level", default="info")
    arguments = parser.parse_args()
    config = uvicorn.Config(
        "incident_copilot.main:app",
        host=arguments.host,
        port=arguments.port,
        log_level=arguments.log_level,
    )
    server = uvicorn.Server(config)
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
