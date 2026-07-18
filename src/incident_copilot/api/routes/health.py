"""Liveness endpoint."""

from typing import cast

from fastapi import APIRouter, Request

from incident_copilot.api.schemas import HealthResponse
from incident_copilot.core.config import Settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without requiring optional external services."""
    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
    )
