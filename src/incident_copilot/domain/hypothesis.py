"""Root-cause hypothesis domain models."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    DomainModel,
    HypothesisStatus,
    SourceType,
    normalize_services,
    unique_non_empty,
)


class VerificationQuery(DomainModel):
    """Provider-neutral query intent used to test a hypothesis later."""

    query: str = Field(min_length=1, max_length=1_000)
    source_types: list[SourceType] = Field(min_length=1, max_length=6)
    service: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("source_types")
    @classmethod
    def unique_source_types(cls, values: list[SourceType]) -> list[SourceType]:
        return list(dict.fromkeys(values))

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_services([value])
        return normalized[0]


class Hypothesis(DomainModel):
    """A falsifiable root-cause claim linked to supporting and opposing evidence."""

    hypothesis_id: str = Field(pattern=r"^hyp_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    description: str = Field(min_length=1, max_length=2_000)
    affected_services: list[str] = Field(default_factory=list, max_length=20)
    supporting_evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    contradicting_evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    verification_queries: list[VerificationQuery] = Field(default_factory=list, max_length=20)
    reasoning_summary: str = Field(min_length=1, max_length=4_000)
    version: int = Field(default=1, ge=1)

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: list[str]) -> list[str]:
        return normalize_services(values)

    @field_validator("supporting_evidence_ids", "contradicting_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        values = unique_non_empty(values, field_name="evidence ids")
        for value in values:
            if not value.startswith("ev_"):
                raise ValueError("evidence ids must start with 'ev_'")
        return values

    @model_validator(mode="after")
    def validate_evidence_relationships(self) -> Self:
        overlap = set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids)
        if overlap:
            raise ValueError("supporting and contradicting evidence must not overlap")
        if self.status is HypothesisStatus.SUPPORTED and not self.supporting_evidence_ids:
            raise ValueError("a supported hypothesis requires supporting evidence")
        return self
