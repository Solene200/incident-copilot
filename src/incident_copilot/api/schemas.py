"""Stable API response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ApiModel(BaseModel):
    """Strict base model for public API schemas."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    """Liveness response that does not probe optional infrastructure."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class ErrorDetail(ApiModel):
    """Machine-readable and safe error description."""

    code: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    """Envelope returned for expected application and validation errors."""

    error: ErrorDetail
    request_id: str
