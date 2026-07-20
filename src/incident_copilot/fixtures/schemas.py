"""不包含 Provider 实现的版本化 Fixture 外层结构。"""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    DomainModel,
    normalize_services,
    unique_evidence_ids,
    unique_non_empty,
)
from incident_copilot.domain.evidence import (
    CONTENT_HASH_ALGORITHM,
    ContentHashAlgorithm,
    Evidence,
)
from incident_copilot.domain.incident import IncidentContext


class FixtureGroundTruth(DomainModel):
    """仅供 Evaluation 使用、与 Agent 可见载荷隔离的真实标签。"""

    # 该离线故障样例预先标注的真实根因。
    root_cause: str = Field(min_length=1, max_length=4_000)
    # 根据标签应被识别为受影响的服务。
    affected_services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 根据标签应与根因相关的 Evidence ID。
    expected_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("expected_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="expected evidence ids")


class IncidentFixture(DomainModel):
    """描述一个确定性事故场景的最小版本化 Fixture 文件。"""

    # Fixture JSON 外层结构的版本。
    schema_version: Literal["1.0"] = "1.0"
    # 全部 Evidence 使用的版本化 canonical content hashing 契约。
    content_hash_algorithm: ContentHashAlgorithm = CONTENT_HASH_ALGORITHM
    # 便于测试和演示引用的样例名称。
    name: str = Field(min_length=1, max_length=128)
    # 对该故障场景和主要症状的简短说明。
    description: str = Field(min_length=1, max_length=1_000)
    # 固定为 False, 防止含敏感数据的 Fixture 通过校验。
    contains_sensitive_data: Literal[False] = False
    # 本地样例中经过校验的故障上下文。
    incident: IncidentContext
    # 本地样例提供给各 Fixture Provider 查询的完整证据。
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple, max_length=1_000)
    # 只供离线 Evaluation 使用、绝不传给 Graph 的真实标签。
    ground_truth: FixtureGroundTruth | None = None
    # 用于分类和筛选 Fixture 的稳定标签。
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="tags")

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> Self:
        if any(
            item.content_hash_algorithm != self.content_hash_algorithm for item in self.evidence
        ):
            raise ValueError("fixture evidence must use the declared content hash algorithm")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("fixture evidence ids must be unique")
        if self.ground_truth is not None:
            missing = set(self.ground_truth.expected_evidence_ids) - set(evidence_ids)
            if missing:
                raise ValueError("ground truth references evidence missing from fixture")
        return self
