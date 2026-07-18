"""FastAPI application factory and default ASGI app."""

from fastapi import FastAPI

from incident_copilot.api.errors import register_exception_handlers
from incident_copilot.api.routes.health import router as health_router
from incident_copilot.core.config import Settings, get_settings
from incident_copilot.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application instance with explicitly injected settings."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
    )
    app.state.settings = resolved_settings
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
