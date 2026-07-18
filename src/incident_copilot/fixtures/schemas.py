"""Versioned fixture envelopes without provider implementation."""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import DomainModel, normalize_services, unique_non_empty
from incident_copilot.domain.evidence import Evidence
from incident_copilot.domain.incident import IncidentContext


class FixtureGroundTruth(DomainModel):
    """Evaluation-only truth kept separate from future agent-visible payloads."""

    root_cause: str = Field(min_length=1, max_length=4_000)
    affected_services: list[str] = Field(default_factory=list, max_length=20)
    expected_evidence_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: list[str]) -> list[str]:
        return normalize_services(values)

    @field_validator("expected_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        return unique_non_empty(values, field_name="expected evidence ids")


class IncidentFixture(DomainModel):
    """Minimal versioned fixture file for one deterministic incident scenario."""

    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1_000)
    contains_sensitive_data: Literal[False] = False
    incident: IncidentContext
    evidence: list[Evidence] = Field(default_factory=list, max_length=1_000)
    ground_truth: FixtureGroundTruth | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        return unique_non_empty(values, field_name="tags")

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> Self:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("fixture evidence ids must be unique")
        if self.ground_truth is not None:
            missing = set(self.ground_truth.expected_evidence_ids) - set(evidence_ids)
            if missing:
                raise ValueError("ground truth references evidence missing from fixture")
        return self
