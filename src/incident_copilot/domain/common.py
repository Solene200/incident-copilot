"""Shared domain types and validation helpers."""

import re
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def require_timezone(value: datetime) -> datetime:
    """Reject naive datetimes at every domain boundary."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone information")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]


class DomainModel(BaseModel):
    """Strict base class for validated domain values."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class Severity(StrEnum):
    """Incident severity independent of a specific observability vendor."""

    UNKNOWN = "unknown"
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class Environment(StrEnum):
    """Deployment environment reported by an incident."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """Canonical evidence source categories."""

    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CHANGE = "change"
    TOPOLOGY = "topology"
    KNOWLEDGE = "knowledge"


class HypothesisStatus(StrEnum):
    """Lifecycle states for a root-cause hypothesis."""

    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ReportDisposition(StrEnum):
    """How strongly a report states its root cause."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    INCONCLUSIVE = "inconclusive"


class RiskLevel(StrEnum):
    """Operational risk attached to a remediation suggestion."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def normalize_services(values: Sequence[str]) -> tuple[str, ...]:
    """Normalize, validate, and de-duplicate service names in input order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip().lower()
        if not value or len(value) > 128:
            raise ValueError("service name must contain 1 to 128 characters")
        if not value[0].isalnum() or any(
            not (character.isalnum() or character in "._-") for character in value
        ):
            raise ValueError(f"invalid service name: {raw_value!r}")
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    return tuple(normalized)


def normalize_optional_service(value: str | None) -> str | None:
    """Normalize one optional service name with the shared service-name contract."""
    if value is None:
        return None
    return normalize_services((value,))[0]


def unique_non_empty(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    """Strip and de-duplicate bounded string collections."""
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{field_name} must not contain empty values")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def unique_evidence_ids(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    """Validate and de-duplicate references to evidence domain objects."""
    result = unique_non_empty(values, field_name=field_name)
    for value in result:
        if re.fullmatch(r"ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is None:
            raise ValueError(f"{field_name} must contain valid evidence ids")
    return result
