"""证据和引用领域模型。"""

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
    """能够把报告陈述解析回原始来源的稳定定位信息。"""

    # 引用记录的唯一标识, 统一使用 cit_ 前缀。
    citation_id: str = Field(pattern=r"^cit_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 原始数据的可解析地址, 例如内部路径或 HTTP URL。
    uri: str = Field(min_length=1, max_length=2_048)
    # 在 URI 对应资源中进一步定位内容的位置说明。
    locator: str = Field(min_length=1, max_length=1_024)
    # 报告和界面上向人展示的来源名称。
    display_name: str = Field(min_length=1, max_length=256)
    # 系统取得这条来源内容的 UTC 时间。
    retrieved_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # 来源内容的 SHA-256, 用于验证引用内容没有被替换。
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
    """保存在有界 Graph State 之外的完整证据。"""

    # 完整证据的唯一标识, 统一使用 ev_ 前缀。
    evidence_id: str = Field(pattern=r"^ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 证据属于日志、指标、Trace、变更、拓扑还是知识。
    source_type: SourceType
    # 产生证据的具体 Provider 或数据源名称。
    source_name: str = Field(min_length=1, max_length=128)
    # 便于人快速识别证据的短标题。
    title: str = Field(min_length=1, max_length=256)
    # Provider 返回的完整原始证据载荷。
    content: JsonValue
    # 写入 State 和报告前使用的有界证据摘要。
    summary: str = Field(min_length=1, max_length=2_000)
    # 单点事件发生时间, 区间证据可以不使用此字段。
    timestamp: AwareDatetime | None = None
    # 区间证据覆盖的开始时间。
    start_time: AwareDatetime | None = None
    # 区间证据覆盖的结束时间。
    end_time: AwareDatetime | None = None
    # 这条证据直接关联的服务名称。
    service: str | None = Field(default=None, min_length=1, max_length=128)
    # 证据与当前调查问题的相关程度, 范围为 0 到 1。
    relevance_score: float = Field(ge=0.0, le=1.0)
    # 数据源本身的可信程度, 范围为 0 到 1。
    reliability_score: float = Field(ge=0.0, le=1.0)
    # 指标名、操作名等来源专属的补充结构化信息。
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    # 能够重新定位这条证据原始来源的引用。
    citation: Citation
    # 完整 content 的 SHA-256, 必须与 Citation 中的哈希一致。
    content_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    # Provider 实际收集到这条证据的 UTC 时间。
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
    """适合 Graph State 和报告响应使用的有界投影。"""

    # 指向完整 Evidence 的唯一标识。
    evidence_id: str = Field(pattern=r"^ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 被引用证据的来源类别。
    source_type: SourceType
    # 被引用证据的短标题。
    title: str = Field(min_length=1, max_length=256)
    # 适合存入有界 Graph State 的证据摘要。
    summary: str = Field(min_length=1, max_length=2_000)
    # 单点证据的发生时间。
    timestamp: AwareDatetime | None = None
    # 区间证据的开始时间。
    start_time: AwareDatetime | None = None
    # 区间证据的结束时间。
    end_time: AwareDatetime | None = None
    # 被引用证据关联的服务。
    service: str | None = Field(default=None, min_length=1, max_length=128)
    # 被引用证据与调查的相关性评分。
    relevance_score: float = Field(ge=0.0, le=1.0)
    # 被引用证据来源的可靠性评分。
    reliability_score: float = Field(ge=0.0, le=1.0)
    # 保留下来的原始来源定位信息。
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
        """创建经过刻意裁剪的 State 和报告投影。"""
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
