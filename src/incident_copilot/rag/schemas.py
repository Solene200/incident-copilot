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

    RUNBOOK = "runbook"
    SERVICE = "service"
    INCIDENT = "incident"
    ERROR_CODE = "error_code"
    ALERT = "alert"
    RELEASE_POLICY = "release_policy"


class KnowledgeDocument(DomainModel):
    """语义切分前的一份已校验源文档。"""

    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    document_type: DocumentType
    title: str = Field(min_length=1, max_length=256)
    source_uri: str = Field(min_length=1, max_length=2_048)
    service_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    environment_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    version: str = Field(min_length=1, max_length=64)
    effective_at: AwareDatetime
    ingested_at: AwareDatetime
    content: str = Field(min_length=1, max_length=200_000)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
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

    chunk_id: str = Field(pattern=r"^chunk_[A-Za-z0-9][A-Za-z0-9_-]{0,160}$")
    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    document_type: DocumentType
    document_title: str = Field(min_length=1, max_length=256)
    ordinal: int = Field(ge=0, le=10_000)
    text: str = Field(min_length=1, max_length=20_000)
    token_count: int = Field(ge=1, le=10_000)
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    service_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    environment_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    version: str = Field(min_length=1, max_length=64)
    effective_at: AwareDatetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
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

    chunk: KnowledgeChunk
    embedding: tuple[float, ...] = Field(min_length=1, max_length=4_096)
    embedding_model: str = Field(min_length=1, max_length=128)
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

    chunk: KnowledgeChunk
    score: float = Field(ge=0.0)


class IngestResult(DomainModel):
    """一次幂等摄取操作后实际测量的索引状态。"""

    input_document_count: int = Field(ge=0)
    indexed_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    embedded_chunk_count: int = Field(ge=0)


class MetadataFilter(DomainModel):
    """所有检索后端共享的白名单元数据约束。"""

    services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    environments: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    document_types: tuple[DocumentType, ...] = Field(default_factory=tuple, max_length=10)
    effective_before: AwareDatetime | None = None
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

    query: str = Field(min_length=2, max_length=512)
    top_k: int = Field(default=5, ge=1, le=50)
    metadata_filter: MetadataFilter = Field(default_factory=MetadataFilter)

    @field_validator("query")
    @classmethod
    def validate_searchable_query(cls, value: str) -> str:
        if SEARCH_TOKEN_PATTERN.search(value) is None:
            raise ValueError("query must contain at least one searchable token")
        return value


class SearchHit(DomainModel):
    """带有原始可解析引用的排序混合检索结果。"""

    chunk: KnowledgeChunk
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1, le=50)
    matched_by: tuple[str, ...] = Field(min_length=1, max_length=4)

    @field_validator("matched_by")
    @classmethod
    def normalize_match_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="match sources")


class RetrievalResult(DomainModel):
    """包含透明查询改写的确定性检索响应。"""

    original_query: str = Field(min_length=2, max_length=512)
    rewritten_query: str = Field(min_length=2, max_length=1_024)
    hits: tuple[SearchHit, ...] = Field(default_factory=tuple, max_length=50)
    indexed_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
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
