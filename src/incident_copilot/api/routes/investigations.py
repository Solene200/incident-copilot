"""Investigation creation, status, SSE, and human resume endpoints."""

from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Header, Request, Response, status
from starlette.responses import StreamingResponse

from incident_copilot.api.investigation_schemas import (
    CreateInvestigationRequest,
    InvestigationResponse,
    ResumeInvestigationRequest,
)
from incident_copilot.core.config import Settings
from incident_copilot.core.exceptions import DomainValidationError
from incident_copilot.investigations.models import InvestigationEvent, InvestigationStatus
from incident_copilot.investigations.service import InvestigationService

router = APIRouter(prefix="/v1/investigations", tags=["investigations"])
_STREAM_END_STATUSES = {
    InvestigationStatus.WAITING_REVIEW,
    InvestigationStatus.COMPLETED,
    InvestigationStatus.FAILED,
}


def _service(request: Request) -> InvestigationService:
    return cast(InvestigationService, request.app.state.investigation_service)


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_investigation(
    payload: CreateInvestigationRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ] = None,
) -> InvestigationResponse:
    """Create an asynchronous investigation using an optional idempotency key."""
    incident = payload.to_incident(f"inc_{uuid4().hex}")
    record, created = await _service(request).create(
        incident=incident,
        options=payload.options,
        request_fingerprint=payload.fingerprint(),
        idempotency_key=idempotency_key,
    )
    settings = cast(Settings, request.app.state.settings)
    response.headers["Location"] = (
        f"{settings.api_prefix}/v1/investigations/{record.investigation_id}"
    )
    return InvestigationResponse.from_record(record, replayed=not created)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: str, request: Request) -> InvestigationResponse:
    """Return the current task status and report projection when available."""
    record = await _service(request).get(investigation_id)
    return InvestigationResponse.from_record(record)


@router.post(
    "/{investigation_id}/resume",
    response_model=InvestigationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_investigation(
    investigation_id: str,
    payload: ResumeInvestigationRequest,
    request: Request,
) -> InvestigationResponse:
    """Resume one paused checkpoint with an allow-listed human decision."""
    record = await _service(request).resume(investigation_id, payload)
    return InvestigationResponse.from_record(record)


@router.get("/{investigation_id}/events")
async def stream_investigation_events(
    investigation_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream ordered safe events and support reconnection from the last event ID."""
    service = _service(request)
    await service.get(investigation_id)
    after_sequence = _parse_last_event_id(investigation_id, last_event_id)
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        _event_stream(
            service,
            investigation_id,
            request,
            after_sequence=after_sequence,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_stream(
    service: InvestigationService,
    investigation_id: str,
    request: Request,
    *,
    after_sequence: int,
    heartbeat_seconds: float,
) -> AsyncIterator[str]:
    sequence = after_sequence
    while True:
        events = await service.repository.list_events(
            investigation_id,
            after_sequence=sequence,
        )
        for event in events:
            yield _format_sse(event)
            sequence = event.sequence
        record = await service.get(investigation_id)
        if record.status in _STREAM_END_STATUSES:
            return
        if await request.is_disconnected():
            return
        events = await service.repository.wait_for_events(
            investigation_id,
            after_sequence=sequence,
            timeout_seconds=heartbeat_seconds,
        )
        if not events:
            yield ": heartbeat\n\n"


def _format_sse(event: InvestigationEvent) -> str:
    payload = event.model_dump_json()
    return f"id: {event.event_id}\nevent: {event.event_type.value}\ndata: {payload}\n\n"


def _parse_last_event_id(investigation_id: str, value: str | None) -> int:
    if value is None:
        return 0
    prefix = f"evt_{investigation_id.removeprefix('inv_')}_"
    if not value.startswith(prefix):
        raise DomainValidationError("Last-Event-ID does not belong to this investigation")
    sequence_text = value.removeprefix(prefix)
    if not sequence_text.isdigit() or int(sequence_text) < 1:
        raise DomainValidationError("Last-Event-ID is invalid")
    return int(sequence_text)
