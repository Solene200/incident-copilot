"""Strict inputs and outputs for read-only investigation tools."""

from datetime import timedelta
from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    normalize_optional_service,
)
from incident_copilot.domain.evidence import Evidence

MAX_QUERY_WINDOW = timedelta(hours=24)


class QueryContext(DomainModel):
    """Per-call controls supplied by orchestration without leaking graph state."""

    correlation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    deadline: AwareDatetime
    remaining_tool_calls: int = Field(ge=0, le=1_000)


class ToolInput(DomainModel):
    """Base input enforcing the shared normalized service contract."""

    service: str = Field(min_length=1, max_length=128)

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str) -> str:
        normalized = normalize_optional_service(value)
        if normalized is None:  # pragma: no cover - required field prevents this path
            raise ValueError("service is required")
        return normalized


class TimeRangeToolInput(ToolInput):
    """Shared bounded time range and result limit."""

    start_time: AwareDatetime
    end_time: AwareDatetime
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        if self.end_time - self.start_time > MAX_QUERY_WINDOW:
            raise ValueError("query window must not exceed 24 hours")
        return self


class SearchLogsInput(TimeRangeToolInput):
    """Validated log search intent independent of vendor query syntax."""

    query: str | None = Field(default=None, min_length=1, max_length=256)


class QueryMetricsInput(TimeRangeToolInput):
    """Validated request for a pre-aggregated metric series."""

    metric_name: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{0,127}$")
    aggregation: str = Field(default="max", pattern=r"^(avg|max|min|p95|rate)$")


class QueryTracesInput(TimeRangeToolInput):
    """Validated trace search filters."""

    operation: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern=r"^(ok|error|timeout)$")


class GetServiceTopologyInput(ToolInput):
    """Validated point-in-time topology lookup."""

    at_time: AwareDatetime
    depth: int = Field(default=1, ge=1, le=3)
    limit: int = Field(default=20, ge=1, le=50)


class GetRecentChangesInput(TimeRangeToolInput):
    """Validated deployment and configuration change lookup."""

    change_type: str | None = Field(
        default=None,
        pattern=r"^(deployment|configuration|feature_flag|infrastructure)$",
    )


class SearchRunbooksInput(ToolInput):
    """Validated runbook search request."""

    query: str = Field(min_length=2, max_length=256)
    limit: int = Field(default=5, ge=1, le=20)


class SearchSimilarIncidentsInput(ToolInput):
    """Validated historical incident search request."""

    query: str = Field(min_length=2, max_length=256)
    before_time: AwareDatetime
    lookback_days: int = Field(default=90, ge=1, le=365)
    limit: int = Field(default=5, ge=1, le=20)


class ToolExecutionResult(DomainModel):
    """Measured result returned by the unified registry wrapper."""

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple, max_length=50)
    attempts: int = Field(ge=1, le=10)
    duration_ms: int = Field(ge=0)
