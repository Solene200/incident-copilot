"""FastAPI application factory and default ASGI app."""

from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver

from incident_copilot.api.errors import register_exception_handlers
from incident_copilot.api.routes.health import router as health_router
from incident_copilot.api.routes.investigations import router as investigations_router
from incident_copilot.core.config import Settings, get_settings
from incident_copilot.core.logging import configure_logging
from incident_copilot.graph.bootstrap import build_offline_investigation_graph
from incident_copilot.investigations.repository import InMemoryInvestigationRepository
from incident_copilot.investigations.service import InvestigationService


def create_app(
    settings: Settings | None = None,
    investigation_service: InvestigationService | None = None,
) -> FastAPI:
    """Build an application instance with explicitly injected settings."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
    )
    app.state.settings = resolved_settings
    app.state.investigation_service = investigation_service or InvestigationService(
        graph=build_offline_investigation_graph(
            checkpointer=InMemorySaver(),
            require_human_review=True,
        ),
        repository=InMemoryInvestigationRepository(),
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(investigations_router, prefix=resolved_settings.api_prefix)
    return app


app = create_app()
