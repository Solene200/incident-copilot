"""经过校验的知识文档、Chunk 和检索值对象。"""

import hashlib
import math
import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    normalize_services,
    unique_non_empty,
)
from incident_copilot.domain.evidence import Citation

# RAG 分词和查询校验共同使用的英文标识符与中文字符规则。
SEARCH_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.:/-]+|[\u4e00-\u9fff]")


def normalize_document_text(value: str) -> str:
    """计算哈希或切分前规范化换行符和行尾空白。"""
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines).strip()
    if not normalized:
        raise ValueError("knowledge content must not be empty")
    return normalized


def content_sha256(value: str) -> str:
    """返回用于文档和 Chunk 幂等性的规范 SHA-256。"""
    return hashlib.sha256(normalize_document_text(value).encode("utf-8")).hexdigest()


class DocumentType(StrEnum):
    """Phase 3 语料支持的知识类别。"""

    RUNBOOK = "runbook"  # 故障排查和处置手册。
    SERVICE = "service"  # 服务职责、依赖和运行说明。
    INCIDENT = "incident"  # 已经结束并复盘的历史故障。
    ERROR_CODE = "error_code"  # 错误码含义和处理建议。
    ALERT = "alert"  # 告警规则、阈值和解释。
    RELEASE_POLICY = "release_policy"  # 发布、回滚和变更策略。


class KnowledgeDocument(DomainModel):
    """语义切分前的一份已校验源文档。"""

    # 原始知识文档的唯一标识, 统一使用 doc_ 前缀。
    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 文档属于 Runbook、服务说明还是历史故障等类别。
    document_type: DocumentType
    # 向读者展示的知识文档标题。
    title: str = Field(min_length=1, max_length=256)
    # 可以重新定位原始文档的安全 URI。
    source_uri: str = Field(min_length=1, max_length=2_048)
    # 该文档适用的服务名称标签。
    service_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 该文档适用的部署环境标签。
    environment_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 文档自身的业务版本。
    version: str = Field(min_length=1, max_length=64)
    # 文档内容开始生效的时间。
    effective_at: AwareDatetime
    # 文档被当前索引摄取的时间。
    ingested_at: AwareDatetime
    # 去除 TOML Frontmatter 后的完整 Markdown 正文。
    content: str = Field(min_length=1, max_length=200_000)
    # 规范化正文的 SHA-256, 用于幂等摄取。
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    # 文档类型专属的其他安全元数据。
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return normalize_document_text(value)

    @field_validator("source_uri")
    @classmethod
    def validate_source_uri(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"fixture", "internal", "http", "https"}:
            raise ValueError("knowledge source_uri uses an unsupported scheme")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("knowledge source_uri must not contain credentials")
        if parsed.scheme in {"http", "https"} and parsed.hostname is None:
            raise ValueError("HTTP knowledge source_uri must contain a host")
        if parsed.scheme in {"fixture", "internal"} and not parsed.netloc and not parsed.path:
            raise ValueError("knowledge source_uri must contain a source location")
        return value

    @field_validator("service_tags")
    @classmethod
    def normalize_service_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("environment_tags")
    @classmethod
    def normalize_environment_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip().lower() for value in values)
        return unique_non_empty(normalized, field_name="environment tags")

    @model_validator(mode="after")
    def validate_content_hash(self) -> Self:
        if content_sha256(self.content) != self.content_hash:
            raise ValueError("knowledge document content_hash does not match content")
        return self


class KnowledgeChunk(DomainModel):
    """语义切分生成的有界且保留引用的单元。"""

    # 切分后知识块的稳定唯一标识。
    chunk_id: str = Field(pattern=r"^chunk_[A-Za-z0-9][A-Za-z0-9_-]{0,160}$")
    # 该 Chunk 所属的原始 KnowledgeDocument ID。
    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 继承自原始文档的知识类别。
    document_type: DocumentType
    # 继承自原始文档的展示标题。
    document_title: str = Field(min_length=1, max_length=256)
    # 该 Chunk 在原始文档切分结果中的从零开始序号。
    ordinal: int = Field(ge=0, le=10_000)
    # 包含章节路径前缀的规范化 Chunk 正文。
    text: str = Field(min_length=1, max_length=20_000)
    # 项目确定性 tokenizer 计算的近似 Token 数。
    token_count: int = Field(ge=1, le=10_000)
    # 从 Markdown 标题栈继承的章节层级路径。
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 继承自原文档的服务标签。
    service_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 继承自原文档的环境标签。
    environment_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 继承自原文档的业务版本。
    version: str = Field(min_length=1, max_length=64)
    # 继承自原文档的生效时间。
    effective_at: AwareDatetime
    # 继承自原文档的其他元数据。
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    # 规范化 Chunk 文本的 SHA-256。
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    # 能定位到原文档章节和 Chunk 序号的引用。
    citation: Citation

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_document_text(value)

    @field_validator("service_tags")
    @classmethod
    def normalize_service_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("environment_tags", "section_path")
    @classmethod
    def normalize_string_collections(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="chunk metadata")

    @model_validator(mode="after")
    def validate_hash_and_citation(self) -> Self:
        if content_sha256(self.text) != self.content_hash:
            raise ValueError("knowledge chunk content_hash does not match text")
        if self.citation.content_hash != self.content_hash:
            raise ValueError("knowledge chunk citation hash does not match content")
        return self


class EmbeddedChunk(DomainModel):
    """与一个版本化 Embedding 向量配对的知识 Chunk。"""

    # 与向量绑定的完整知识 Chunk。
    chunk: KnowledgeChunk
    # Embedding 模型生成的有限非零向量。
    embedding: tuple[float, ...] = Field(min_length=1, max_length=4_096)
    # 生成向量的模型名称, 防止混用不同向量空间。
    embedding_model: str = Field(min_length=1, max_length=128)
    # 生成向量的模型版本。
    embedding_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_embedding(self) -> Self:
        if any(not math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding values must be finite")
        if not any(value != 0 for value in self.embedding):
            raise ValueError("embedding must not be a zero vector")
        return self


class ScoredChunk(DomainModel):
    """倒数排名融合前的后端内部候选。"""

    # 当前检索后端命中的知识 Chunk。
    chunk: KnowledgeChunk
    # 当前检索后端计算的原始非负分数。
    score: float = Field(ge=0.0)


class IngestResult(DomainModel):
    """一次幂等摄取操作后实际测量的索引状态。"""

    # 本次摄取调用收到的文档数量。
    input_document_count: int = Field(ge=0)
    # 摄取完成后索引中的文档总数。
    indexed_document_count: int = Field(ge=0)
    # 摄取完成后索引中的 Chunk 总数。
    indexed_chunk_count: int = Field(ge=0)
    # 本次新生成并写入向量存储的 Chunk 数量。
    embedded_chunk_count: int = Field(ge=0)


class MetadataFilter(DomainModel):
    """所有检索后端共享的白名单元数据约束。"""

    # 只保留至少匹配一个服务标签的 Chunk。
    services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 只保留至少匹配一个环境标签的 Chunk。
    environments: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    # 只保留属于这些知识文档类别的 Chunk。
    document_types: tuple[DocumentType, ...] = Field(default_factory=tuple, max_length=10)
    # 只保留生效时间严格早于该时间点的 Chunk。
    effective_before: AwareDatetime | None = None
    # 只保留生效时间严格晚于该时间点的 Chunk。
    effective_after: AwareDatetime | None = None

    @field_validator("services")
    @classmethod
    def normalize_services_filter(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("environments")
    @classmethod
    def normalize_environment_filter(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip().lower() for value in values)
        return unique_non_empty(normalized, field_name="environment filter")

    @model_validator(mode="after")
    def validate_effective_window(self) -> Self:
        if (
            self.effective_before is not None
            and self.effective_after is not None
            and self.effective_after >= self.effective_before
        ):
            raise ValueError("effective_after must be earlier than effective_before")
        return self


class SearchQuery(DomainModel):
    """不依赖具体索引后端的有界检索请求。"""

    # 用户原始知识检索问题。
    query: str = Field(min_length=2, max_length=512)
    # 融合去重后最多返回的最终命中数。
    top_k: int = Field(default=5, ge=1, le=50)
    # BM25 和向量检索共同执行的元数据过滤条件。
    metadata_filter: MetadataFilter = Field(default_factory=MetadataFilter)

    @field_validator("query")
    @classmethod
    def validate_searchable_query(cls, value: str) -> str:
        if SEARCH_TOKEN_PATTERN.search(value) is None:
            raise ValueError("query must contain at least one searchable token")
        return value


class SearchHit(DomainModel):
    """带有原始可解析引用的排序混合检索结果。"""

    # 混合检索最终命中的知识 Chunk。
    chunk: KnowledgeChunk
    # RRF 融合后归一化到 0 到 1 的分数。
    score: float = Field(ge=0.0, le=1.0)
    # 该命中在最终结果中的从 1 开始排名。
    rank: int = Field(ge=1, le=50)
    # 命中来自 bm25、vector 或两者共同召回。
    matched_by: tuple[str, ...] = Field(min_length=1, max_length=4)

    @field_validator("matched_by")
    @classmethod
    def normalize_match_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="match sources")


class RetrievalResult(DomainModel):
    """包含透明查询改写的确定性检索响应。"""

    # 调用方提交的原始查询文本。
    original_query: str = Field(min_length=2, max_length=512)
    # 加入确定性别名后的实际检索文本。
    rewritten_query: str = Field(min_length=2, max_length=1_024)
    # 排序、融合并按内容哈希去重后的命中。
    hits: tuple[SearchHit, ...] = Field(default_factory=tuple, max_length=50)
    # 查询时索引中实际存在的文档总数。
    indexed_document_count: int = Field(ge=0)
    # 查询时索引中实际存在的 Chunk 总数。
    indexed_chunk_count: int = Field(ge=0)
    # 系统生成本次检索结果的时间。
    retrieved_at: AwareDatetime


def chunk_matches_filter(chunk: KnowledgeChunk, metadata_filter: MetadataFilter) -> bool:
    """对词法候选和向量候选应用完全相同的元数据策略。"""
    if metadata_filter.services and not set(metadata_filter.services).intersection(
        chunk.service_tags
    ):
        return False
    if metadata_filter.environments and not set(metadata_filter.environments).intersection(
        chunk.environment_tags
    ):
        return False
    if metadata_filter.document_types and chunk.document_type not in metadata_filter.document_types:
        return False
    if (
        metadata_filter.effective_before is not None
        and chunk.effective_at >= metadata_filter.effective_before
    ):
        return False
    return not (
        metadata_filter.effective_after is not None
        and chunk.effective_at <= metadata_filter.effective_after
    )
