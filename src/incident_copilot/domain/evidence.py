"""Evidence and citation domain models."""

from datetime import UTC, datetime
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    SourceType,
    normalize_optional_service,
)


class Citation(DomainModel):
    """Stable locator that can resolve a report statement back to its source."""

    citation_id: str = Field(pattern=r"^cit_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    uri: str = Field(min_length=1, max_length=2_048)
    locator: str = Field(min_length=1, max_length=1_024)
    display_name: str = Field(min_length=1, max_length=256)
    retrieved_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"fixture", "internal", "http", "https"}:
            raise ValueError("citation uri must use fixture, internal, http, or https scheme")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("citation uri must not contain credentials")
        if parsed.scheme in {"http", "https"} and parsed.hostname is None:
            raise ValueError("http citation uri must contain a host")
        if parsed.scheme in {"fixture", "internal"} and not parsed.netloc and not parsed.path:
            raise ValueError("citation uri must contain a source location")
        return value


class Evidence(DomainModel):
    """Full evidence retained outside the future bounded graph state."""

    evidence_id: str = Field(pattern=r"^ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    content: JsonValue
    summary: str = Field(min_length=1, max_length=2_000)
    timestamp: AwareDatetime | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    service: str | None = Field(default=None, min_length=1, max_length=128)
    relevance_score: float = Field(ge=0.0, le=1.0)
    reliability_score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    citation: Citation
    content_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    collected_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str | None) -> str | None:
        return normalize_optional_service(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("evidence start_time must be earlier than end_time")
        if self.citation.content_hash.lower() != self.content_hash.lower():
            raise ValueError("citation and evidence content hashes must match")
        return self


class EvidenceRef(DomainModel):
    """Bounded projection suitable for graph state and report responses."""

    evidence_id: str = Field(pattern=r"^ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    source_type: SourceType
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=2_000)
    timestamp: AwareDatetime | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    service: str | None = Field(default=None, min_length=1, max_length=128)
    relevance_score: float = Field(ge=0.0, le=1.0)
    reliability_score: float = Field(ge=0.0, le=1.0)
    citation: Citation

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str | None) -> str | None:
        return normalize_optional_service(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("evidence reference start_time must be earlier than end_time")
        return self

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> Self:
        """Create the deliberately small state/report projection."""
        return cls(
            evidence_id=evidence.evidence_id,
            source_type=evidence.source_type,
            title=evidence.title,
            summary=evidence.summary,
            timestamp=evidence.timestamp,
            start_time=evidence.start_time,
            end_time=evidence.end_time,
            service=evidence.service,
            relevance_score=evidence.relevance_score,
            reliability_score=evidence.reliability_score,
            citation=evidence.citation,
        )
