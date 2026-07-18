"""Shared domain types and validation helpers."""

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
        validate_assignment=True,
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


def normalize_services(values: list[str]) -> list[str]:
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
    return normalized


def unique_non_empty(values: list[str], *, field_name: str) -> list[str]:
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
    return result
