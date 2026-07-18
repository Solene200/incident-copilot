"""FastAPI exception-to-response mappings."""

import logging
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import JsonValue
from starlette.responses import JSONResponse

from incident_copilot.api.schemas import ErrorDetail, ErrorResponse
from incident_copilot.core.exceptions import IncidentCopilotError
from incident_copilot.core.logging import redact_text, redact_value

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"


async def handle_application_error(request: Request, exc: Exception) -> JSONResponse:
    """Map a known application exception to the public error envelope."""
    if not isinstance(exc, IncidentCopilotError):
        raise exc
    response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code.value,
            message=redact_text(exc.message),
            details=cast(dict[str, JsonValue], redact_value(exc.details)),
        ),
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=exc.status_code, content=response.model_dump(mode="json"))


async def handle_request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Return validation failures without echoing potentially sensitive inputs."""
    if not isinstance(exc, RequestValidationError):
        raise exc
    issues: list[dict[str, JsonValue]] = []
    for error in exc.errors():
        location = [
            str(part) if not isinstance(part, int) else part for part in error.get("loc", ())
        ]
        issues.append(
            {
                "type": str(error.get("type", "validation_error")),
                "loc": cast(JsonValue, location),
                "msg": str(error.get("msg", "Invalid value")),
            }
        )
    response = ErrorResponse(
        error=ErrorDetail(
            code="request_validation_error",
            message="Request validation failed",
            details={"issues": cast(JsonValue, issues)},
        ),
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures and return a non-sensitive stable envelope."""
    request_id = _request_id(request)
    logger.error(
        "Unhandled application error",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path},
    )
    response = ErrorResponse(
        error=ErrorDetail(code="internal_error", message="Internal server error"),
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=response.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Install all application-owned exception handlers."""
    app.add_exception_handler(IncidentCopilotError, handle_application_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
