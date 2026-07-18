"""内存和参数化 pgvector 存储的契约测试。"""

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.rag.embeddings import FakeEmbedding
from incident_copilot.rag.loader import MarkdownDocumentLoader
from incident_copilot.rag.schemas import (
    DocumentType,
    EmbeddedChunk,
    MetadataFilter,
)
from incident_copilot.rag.splitter import MarkdownSplitter
from incident_copilot.rag.vector_store import InMemoryVectorStore, PgVectorStore


def embedded_records() -> tuple[EmbeddedChunk, ...]:
    root = Path(__file__).parents[3] / "data" / "knowledge"
    documents = MarkdownDocumentLoader(root).load()
    chunks = MarkdownSplitter().split_documents(documents)
    embedding = FakeEmbedding(dimension=32)
    return tuple(
        EmbeddedChunk(
            chunk=chunk,
            embedding=embedding.embed(chunk.text),
            embedding_model=embedding.model_name,
            embedding_version=embedding.version,
        )
        for chunk in chunks
    )


class RecordingSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.fetched: list[tuple[str, tuple[object, ...]]] = []
        self.rows: list[Mapping[str, object]] = []
        self.transaction_count = 0

    def execute(self, statement: str, parameters: Sequence[object] = ()) -> None:
        self.executed.append((statement, tuple(parameters)))

    def fetch_all(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> Sequence[Mapping[str, object]]:
        self.fetched.append((statement, tuple(parameters)))
        return self.rows

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.transaction_count += 1
        yield


def test_in_memory_vector_store_upsert_search_filter_delete_and_dimension() -> None:
    records = embedded_records()
    embedding = FakeEmbedding(dimension=32)
    store = InMemoryVectorStore(dimension=32)

    assert store.upsert(records) == len(records)
    assert store.upsert(records) == len(records)
    assert store.size == len(records)
    results = store.search(
        embedding.embed("database connection pool timeout"),
        embedding_model=embedding.model_name,
        embedding_version=embedding.version,
        top_k=5,
        metadata_filter=MetadataFilter(
            services=("payment-service",),
            document_types=(DocumentType.RUNBOOK,),
        ),
    )

    assert results
    assert all(item.score >= 0 for item in results)
    assert all(item.chunk.document_type is DocumentType.RUNBOOK for item in results)
    deleted = store.delete_documents(("doc_runbook_payment_gateway_latency",))
    assert deleted > 0
    assert store.size == len(records) - deleted
    with pytest.raises(ValueError, match="dimension"):
        store.search(
            (1.0, 2.0),
            embedding_model=embedding.model_name,
            embedding_version=embedding.version,
            top_k=1,
            metadata_filter=MetadataFilter(),
        )


def test_vector_store_rejects_invalid_vectors_atomically_and_filters_embedding_version() -> None:
    record = embedded_records()[0]
    store = InMemoryVectorStore(dimension=32)
    invalid = record.model_copy(update={"embedding": (float("nan"),) * 32})

    with pytest.raises(ValueError, match="finite"):
        store.upsert((record, invalid))
    assert store.size == 0

    store.upsert((record,))
    assert (
        store.search(
            record.embedding,
            embedding_model=record.embedding_model,
            embedding_version="different-version",
            top_k=1,
            metadata_filter=MetadataFilter(),
        )
        == ()
    )


@pytest.mark.parametrize(
    "embedding",
    [(0.0,) * 32, (float("inf"),) * 32],
)
def test_embedded_chunk_rejects_zero_or_non_finite_vector(
    embedding: tuple[float, ...],
) -> None:
    payload = embedded_records()[0].model_dump()
    payload["embedding"] = embedding

    with pytest.raises(ValidationError, match=r"zero vector|finite"):
        EmbeddedChunk.model_validate(payload)


def test_pgvector_adapter_uses_explicit_schema_and_parameterized_queries() -> None:
    session = RecordingSession()
    store = PgVectorStore(session, dimension=32, table="knowledge_chunks_test")
    record = embedded_records()[0]

    assert store.upsert((record,)) == 1
    assert store.replace_documents((record.chunk.document_id,), (record,)) == 1
    session.rows = [
        {
            "payload": json.dumps(record.model_dump(mode="json")),
            "score": 0.75,
        }
    ]
    results = store.search(
        record.embedding,
        embedding_model=record.embedding_model,
        embedding_version=record.embedding_version,
        top_k=3,
        metadata_filter=MetadataFilter(
            services=("payment-service",),
            environments=("production",),
            document_types=(DocumentType.RUNBOOK,),
            effective_before=record.chunk.effective_at.replace(year=2027),
        ),
    )

    insert_statement, insert_parameters = session.executed[0]
    assert "ON CONFLICT (chunk_id) DO UPDATE" in insert_statement
    assert "embedding_model" in insert_statement
    assert "embedding_version" in insert_statement
    assert record.chunk.chunk_id in insert_parameters
    search_statement, search_parameters = session.fetched[0]
    assert "service_tags && %s::text[]" in search_statement
    assert "environment_tags && %s::text[]" in search_statement
    assert "document_type = ANY(%s::text[])" in search_statement
    assert "embedding_model = %s" in search_statement
    assert "embedding_version = %s" in search_statement
    assert search_parameters[-1] == 3
    assert session.transaction_count == 1
    assert results[0].chunk == record.chunk
    assert results[0].score == 0.75


def test_pgvector_adapter_rejects_unsafe_table_and_wrong_dimension() -> None:
    session = RecordingSession()
    with pytest.raises(ValueError, match="safe SQL identifier"):
        PgVectorStore(session, dimension=32, table="chunks; DROP TABLE incidents")

    store = PgVectorStore(session, dimension=32)
    with pytest.raises(ValueError, match="dimension"):
        store.search(
            (1.0,),
            embedding_model="test",
            embedding_version="1",
            top_k=1,
            metadata_filter=MetadataFilter(),
        )
