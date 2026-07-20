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

    # 时间线事实发生的时间。
    timestamp: AwareDatetime
    # 对该时刻发生事件的简短描述。
    description: str = Field(min_length=1, max_length=1_000)
    # 支撑这条时间线事实的 Evidence ID。
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="timeline evidence ids")


class RejectedHypothesis(DomainModel):
    """对已被证据排除的假设进行简要说明。"""

    # 被排除假设的唯一标识。
    hypothesis_id: str = Field(pattern=r"^hyp_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 被排除假设原本描述的可能根因。
    description: str = Field(min_length=1, max_length=2_000)
    # 根据证据排除该假设的原因。
    rejection_reason: str = Field(min_length=1, max_length=2_000)
    # 支撑排除结论的 Evidence ID。
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="rejected hypothesis evidence ids")


class RemediationStep(DomainModel):
    """需要人工审核的修复建议,本身绝不是可执行操作。"""

    # 建议人工执行的修复动作, 该字段本身不会自动执行。
    action: str = Field(min_length=1, max_length=2_000)
    # 修复步骤的执行优先级, 数字越小越优先。
    priority: int = Field(ge=1, le=100)
    # 执行该修复动作可能带来的风险等级。
    risk_level: RiskLevel
    # 执行后用于确认修复是否有效的验证方法。
    validation: str = Field(min_length=1, max_length=2_000)
    # 修复产生负面影响时的回滚方法。
    rollback: str = Field(min_length=1, max_length=2_000)
    # 是否必须经人工批准, 当前建议默认全部需要。
    requires_human_approval: bool = True


class InvestigationStats(DomainModel):
    """实际测量的调查用量,这些数值绝不推断为评估质量。"""

    # 本次调查实际执行的研究轮数。
    research_rounds: int = Field(ge=0)
    # 本次调查终止的逻辑工具步骤总数。
    tool_call_count: int = Field(ge=0)
    # 本次调查实际消耗的物理 Provider 尝试总数,包含 retry。
    tool_attempt_count: int = Field(ge=0)
    # 成功完成的工具调用数。
    tool_success_count: int = Field(ge=0)
    # 失败或降级的工具调用数。
    tool_failure_count: int = Field(ge=0)
    # 本次调查实际调用模型 Provider 的次数。
    model_call_count: int = Field(ge=0)
    # 模型调用累计输入 Token 数。
    input_tokens: int = Field(ge=0)
    # 模型调用累计输出 Token 数。
    output_tokens: int = Field(ge=0)
    # 输入与输出 Token 之和。
    total_tokens: int = Field(ge=0)
    # Token 数是否来自 Fake Model 的估算而非厂商账单。
    token_usage_estimated: bool = False
    # 调查开始时间。
    started_at: AwareDatetime
    # 调查完成时间, 尚未完成时为 None。
    completed_at: AwareDatetime | None = None
    # 实际调查耗时毫秒数, 尚未完成时为 None。
    duration_ms: int | None = Field(default=None, ge=0)
    # 按证据来源类别统计的 Evidence 数量。
    evidence_count_by_source: Mapping[SourceType, int] = Field(
        default_factory=lambda: MappingProxyType({})
    )
    # Graph 最终停止调查循环的明确原因。
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
        if self.tool_success_count + self.tool_failure_count != self.tool_call_count:
            raise ValueError("tool outcomes must equal tool_call_count")
        if self.tool_attempt_count < self.tool_call_count:
            raise ValueError("tool_attempt_count must not be less than tool_call_count")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if (self.completed_at is None) != (self.duration_ms is None):
            raise ValueError("completed_at and duration_ms must be provided together")
        return self


class IncidentReport(DomainModel):
    """包含有界证据引用且可审计的根因报告。"""

    # 报告数据结构的版本。
    schema_version: Literal["1.0"] = "1.0"
    # 故障报告的唯一标识, 统一使用 rpt_ 前缀。
    report_id: str = Field(pattern=r"^rpt_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 这份报告对应的故障事件标识。
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 面向读者的故障调查结论摘要。
    summary: str = Field(min_length=1, max_length=4_000)
    # 推断出的根因, 无法得出结论时可以为 None。
    root_cause: str | None = Field(default=None, max_length=4_000)
    # 根因是已确认、很可能还是无结论。
    disposition: ReportDisposition
    # 对根因结论的置信度, 范围为 0 到 1。
    confidence: float = Field(ge=0.0, le=1.0)
    # 为什么给出当前置信度的证据化说明。
    confidence_rationale: str = Field(min_length=1, max_length=2_000)
    # 根据证据判断受到影响的服务。
    affected_services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 按发生时间排序的关键事故事实。
    timeline: tuple[TimelineEvent, ...] = Field(default_factory=tuple, max_length=200)
    # 支撑根因结论的轻量 Evidence 引用。
    supporting_evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple, max_length=100)
    # 与根因结论矛盾、需要诚实保留的 Evidence 引用。
    contradicting_evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple, max_length=100)
    # 调查过程中已经被证据排除的其他假设。
    rejected_hypotheses: tuple[RejectedHypothesis, ...] = Field(
        default_factory=tuple, max_length=50
    )
    # 只供人工审核和执行的修复建议集合。
    remediation_steps: tuple[RemediationStep, ...] = Field(default_factory=tuple, max_length=50)
    # 执行修复或解读结论时需要注意的风险。
    risks: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 报告引用的去重来源信息, 必须来自已收集证据。
    citations: tuple[Citation, ...] = Field(default_factory=tuple, max_length=200)
    # 对调查过程、覆盖范围和主要步骤的说明。
    investigation_summary: str = Field(min_length=1, max_length=4_000)
    # 本次调查实际测量的轮数、调用数、Token 和耗时。
    investigation_stats: InvestigationStats
    # 数据源缺失、预算停止等结论限制。
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 系统生成报告的 UTC 时间。
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
