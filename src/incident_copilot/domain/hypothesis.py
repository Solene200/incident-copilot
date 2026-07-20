"""根因假设领域模型。"""

from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    DomainModel,
    HypothesisStatus,
    SourceType,
    normalize_services,
    unique_evidence_ids,
)


class VerificationQuery(DomainModel):
    """供后续验证假设使用的 Provider 无关查询意图。"""

    # 用自然语言描述下一步需要验证的问题。
    query: str = Field(min_length=1, max_length=1_000)
    # 回答该问题需要查询的证据来源类别。
    source_types: tuple[SourceType, ...] = Field(min_length=1, max_length=6)
    # 查询限定的服务, 为 None 时不额外限定服务。
    service: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("source_types")
    @classmethod
    def unique_source_types(cls, values: tuple[SourceType, ...]) -> tuple[SourceType, ...]:
        return tuple(dict.fromkeys(values))

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_services([value])
        return normalized[0]


class Hypothesis(DomainModel):
    """关联支持与反对证据、可以被证伪的根因陈述。"""

    # 根因假设的唯一标识, 统一使用 hyp_ 前缀。
    hypothesis_id: str = Field(pattern=r"^hyp_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 对可能根因的可证伪文字陈述。
    description: str = Field(min_length=1, max_length=2_000)
    # 如果假设成立, 预计会受影响的服务。
    affected_services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 能够支持该假设的 Evidence ID。
    supporting_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    # 能够反驳该假设的 Evidence ID。
    contradicting_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    # 当前对假设成立程度的评分, 范围为 0 到 1。
    confidence: float = Field(ge=0.0, le=1.0)
    # 假设当前处于提出、调查、支持、排除或无结论状态。
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    # 仍需执行的验证查询集合。
    verification_queries: tuple[VerificationQuery, ...] = Field(
        default_factory=tuple, max_length=20
    )
    # 解释当前证据如何影响假设的简短推理摘要。
    reasoning_summary: str = Field(min_length=1, max_length=4_000)
    # 假设每次被重新验证后递增的版本号。
    version: int = Field(default=1, ge=1)

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("supporting_evidence_ids", "contradicting_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="evidence ids")

    @model_validator(mode="after")
    def validate_evidence_relationships(self) -> Self:
        overlap = set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids)
        if overlap:
            raise ValueError("supporting and contradicting evidence must not overlap")
        if self.status is HypothesisStatus.SUPPORTED and not self.supporting_evidence_ids:
            raise ValueError("a supported hypothesis requires supporting evidence")
        return self
