"""结构化事故报告领域模型。"""

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    ReportDisposition,
    RiskLevel,
    SourceType,
    normalize_services,
    unique_evidence_ids,
    unique_non_empty,
)
from incident_copilot.domain.evidence import Citation, EvidenceRef


class TimelineEvent(DomainModel):
    """事故时间线中带有时间戳的一项事实。"""

    timestamp: AwareDatetime
    description: str = Field(min_length=1, max_length=1_000)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="timeline evidence ids")


class RejectedHypothesis(DomainModel):
    """对已被证据排除的假设进行简要说明。"""

    hypothesis_id: str = Field(pattern=r"^hyp_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    description: str = Field(min_length=1, max_length=2_000)
    rejection_reason: str = Field(min_length=1, max_length=2_000)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="rejected hypothesis evidence ids")


class RemediationStep(DomainModel):
    """需要人工审核的修复建议,本身绝不是可执行操作。"""

    action: str = Field(min_length=1, max_length=2_000)
    priority: int = Field(ge=1, le=100)
    risk_level: RiskLevel
    validation: str = Field(min_length=1, max_length=2_000)
    rollback: str = Field(min_length=1, max_length=2_000)
    requires_human_approval: bool = True


class InvestigationStats(DomainModel):
    """实际测量的调查用量,这些数值绝不推断为评估质量。"""

    research_rounds: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    tool_success_count: int = Field(ge=0)
    tool_failure_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    token_usage_estimated: bool = False
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    evidence_count_by_source: Mapping[SourceType, int] = Field(
        default_factory=lambda: MappingProxyType({})
    )
    stop_reason: str = Field(min_length=1, max_length=256)

    @field_validator("evidence_count_by_source")
    @classmethod
    def validate_evidence_counts(cls, values: Mapping[SourceType, int]) -> Mapping[SourceType, int]:
        if any(value < 0 for value in values.values()):
            raise ValueError("evidence counts must be non-negative")
        return MappingProxyType(dict(values))

    @field_serializer("evidence_count_by_source")
    def serialize_evidence_counts(self, values: Mapping[SourceType, int]) -> dict[SourceType, int]:
        return dict(values)

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        if self.tool_success_count + self.tool_failure_count > self.tool_call_count:
            raise ValueError("tool outcomes must not exceed tool_call_count")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if (self.completed_at is None) != (self.duration_ms is None):
            raise ValueError("completed_at and duration_ms must be provided together")
        return self


class IncidentReport(DomainModel):
    """包含有界证据引用且可审计的根因报告。"""

    schema_version: Literal["1.0"] = "1.0"
    report_id: str = Field(pattern=r"^rpt_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    summary: str = Field(min_length=1, max_length=4_000)
    root_cause: str | None = Field(default=None, max_length=4_000)
    disposition: ReportDisposition
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_rationale: str = Field(min_length=1, max_length=2_000)
    affected_services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    timeline: tuple[TimelineEvent, ...] = Field(default_factory=tuple, max_length=200)
    supporting_evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple, max_length=100)
    contradicting_evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple, max_length=100)
    rejected_hypotheses: tuple[RejectedHypothesis, ...] = Field(
        default_factory=tuple, max_length=50
    )
    remediation_steps: tuple[RemediationStep, ...] = Field(default_factory=tuple, max_length=50)
    risks: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    citations: tuple[Citation, ...] = Field(default_factory=tuple, max_length=200)
    investigation_summary: str = Field(min_length=1, max_length=4_000)
    investigation_stats: InvestigationStats
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    generated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("risks", "limitations")
    @classmethod
    def validate_text_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="report list")

    @model_validator(mode="after")
    def validate_report_consistency(self) -> Self:
        if self.disposition is not ReportDisposition.INCONCLUSIVE and not self.root_cause:
            raise ValueError("confirmed or probable reports require a root_cause")
        if list(self.timeline) != sorted(self.timeline, key=lambda item: item.timestamp):
            raise ValueError("timeline must be sorted by timestamp")
        evidence_ids = [item.evidence_id for item in self.supporting_evidence]
        evidence_ids += [item.evidence_id for item in self.contradicting_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("report evidence references must be unique")
        citation_ids = [item.citation_id for item in self.citations]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("report citations must be unique")
        return self
