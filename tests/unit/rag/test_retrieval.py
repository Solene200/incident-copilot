"""查询改写、幂等摄取、RRF、去重和 RAG Provider 测试。"""

import asyncio
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.rag.bm25 import BM25Index
from incident_copilot.rag.bootstrap import build_fixture_retriever
from incident_copilot.rag.embeddings import FakeEmbedding
from incident_copilot.rag.loader import MarkdownDocumentLoader
from incident_copilot.rag.provider import RagKnowledgeProvider
from incident_copilot.rag.retrieval import HybridRetriever
from incident_copilot.rag.rewrite import QueryRewriter
from incident_copilot.rag.schemas import (
    DocumentType,
    EmbeddedChunk,
    MetadataFilter,
    RetrievalResult,
    SearchQuery,
    content_sha256,
)
from incident_copilot.rag.splitter import MarkdownSplitter
from incident_copilot.rag.vector_store import InMemoryVectorStore
from incident_copilot.tools.schemas import (
    QueryContext,
    SearchRunbooksInput,
    SearchSimilarIncidentsInput,
)

FIXED_NOW = datetime(2026, 7, 18, 3, 0, tzinfo=UTC)


class FailingReplaceStore(InMemoryVectorStore):
    def __init__(self, *, dimension: int) -> None:
        super().__init__(dimension=dimension)
        self.fail_replace = False

    def replace_documents(
        self,
        document_ids: Sequence[str],
        records: Sequence[EmbeddedChunk],
    ) -> int:
        if self.fail_replace:
            raise RuntimeError("simulated vector replacement failure")
        return super().replace_documents(document_ids, records)


def knowledge_root() -> Path:
    return Path(__file__).parents[3] / "data" / "knowledge"


def test_query_rewrite_is_transparent_deterministic_bilingual_and_unbiased() -> None:
    rewriter = QueryRewriter()

    first = rewriter.rewrite("库存服务 数据库 连接池 超时")
    second = rewriter.rewrite("库存服务 数据库 连接池 超时")

    assert first == second
    assert "database" in first
    assert "connection" in first
    assert "pool" in first
    assert "timeout" in first
    assert "payment-service" not in first
    assert "acquisition" not in first


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("DNS name lookup timed-out", {"dns", "resolution", "timeout"}),
        ("cache caching regression", {"cache", "regression"}),
        ("db connection issue", {"db", "database", "connection"}),
    ],
)
def test_query_rewrite_normalizes_generic_scenario_synonyms(query: str, expected: set[str]) -> None:
    rewritten = set(QueryRewriter().rewrite(query).split())

    assert expected <= rewritten


def test_search_query_rejects_text_without_searchable_tokens() -> None:
    with pytest.raises(ValidationError, match="searchable token"):
        SearchQuery(query="!!")


def test_ingest_and_hybrid_search_are_idempotent_and_citation_preserving() -> None:
    retriever, initial = build_fixture_retriever(clock=lambda: FIXED_NOW)
    documents = MarkdownDocumentLoader(knowledge_root()).load()
    first = retriever.search(
        SearchQuery(
            query="database connection pool timeout configuration",
            top_k=5,
            metadata_filter=MetadataFilter(
                services=("payment-service",),
                document_types=(DocumentType.RUNBOOK,),
            ),
        )
    )

    repeated_ingest = retriever.ingest(documents)
    second = retriever.search(
        SearchQuery(
            query="database connection pool timeout configuration",
            top_k=5,
            metadata_filter=MetadataFilter(
                services=("payment-service",),
                document_types=(DocumentType.RUNBOOK,),
            ),
        )
    )

    assert initial.indexed_document_count == repeated_ingest.indexed_document_count == 6
    assert initial.indexed_chunk_count == repeated_ingest.indexed_chunk_count
    assert first == second
    assert first.hits[0].chunk.document_id == "doc_runbook_payment_db_pool"
    assert all(hit.chunk.citation.uri.startswith("internal://knowledge/") for hit in first.hits)
    assert all(hit.matched_by for hit in first.hits)
    assert len(first.hits) <= 5


def test_ingest_failure_preserves_previous_retriever_state() -> None:
    embedding = FakeEmbedding(dimension=32)
    store = FailingReplaceStore(dimension=embedding.dimension)
    retriever = HybridRetriever(
        splitter=MarkdownSplitter(),
        embedding=embedding,
        lexical_index=BM25Index(),
        vector_store=store,
        rewriter=QueryRewriter(),
        clock=lambda: FIXED_NOW,
    )
    original = MarkdownDocumentLoader(knowledge_root()).load()[0]
    retriever.ingest((original,))
    before = retriever.search(SearchQuery(query="connection pool timeout", top_k=5))
    replacement_content = "# Replacement\n\nrollback sentinel content"
    replacement = original.model_copy(
        update={
            "content": replacement_content,
            "content_hash": content_sha256(replacement_content),
        }
    )
    store.fail_replace = True

    with pytest.raises(RuntimeError, match="replacement failure"):
        retriever.ingest((replacement,))

    after = retriever.search(SearchQuery(query="connection pool timeout", top_k=5))
    assert after == before
    assert retriever.document_count == 1


def test_hybrid_search_applies_metadata_filter_top_k_and_empty_result() -> None:
    retriever, _ = build_fixture_retriever(clock=lambda: FIXED_NOW)

    incidents = retriever.search(
        SearchQuery(
            query="connection limit reduction incident",
            top_k=2,
            metadata_filter=MetadataFilter(
                services=("payment-service",),
                document_types=(DocumentType.INCIDENT,),
                effective_before=datetime(2026, 7, 18, tzinfo=UTC),
            ),
        )
    )
    empty = retriever.search(
        SearchQuery(
            query="database connection pool",
            top_k=3,
            metadata_filter=MetadataFilter(services=("unknown-service",)),
        )
    )

    assert len(incidents.hits) <= 2
    assert incidents.hits[0].chunk.document_id == "doc_incident_payment_pool_20260628"
    assert all(hit.chunk.document_type is DocumentType.INCIDENT for hit in incidents.hits)
    assert empty.hits == ()


def test_hybrid_search_deduplicates_equal_chunk_content_hashes() -> None:
    retriever, _ = build_fixture_retriever(clock=lambda: FIXED_NOW)
    original = MarkdownDocumentLoader(knowledge_root()).load()[0]
    duplicate = original.model_copy(
        update={
            "document_id": "doc_duplicate_content",
            "source_uri": "internal://knowledge/duplicate.md",
        }
    )

    retriever.ingest((duplicate,))
    result = retriever.search(SearchQuery(query="connection pool timeout", top_k=20))
    hashes = [hit.chunk.content_hash for hit in result.hits]

    assert len(hashes) == len(set(hashes))


@pytest.mark.asyncio
async def test_rag_provider_returns_tool_compatible_evidence() -> None:
    retriever, _ = build_fixture_retriever(clock=lambda: FIXED_NOW)
    provider = RagKnowledgeProvider(retriever)
    context = QueryContext(
        correlation_id="rag-provider-test",
        deadline=datetime(2026, 7, 18, 3, 1, tzinfo=UTC),
        remaining_tool_calls=5,
    )

    runbooks = await provider.search_runbooks(
        SearchRunbooksInput(
            service="payment-service",
            query="database connection pool timeout",
            limit=3,
        ),
        context,
    )
    incidents = await provider.search_similar_incidents(
        SearchSimilarIncidentsInput(
            service="payment-service",
            query="connection limit incident",
            before_time=datetime(2026, 7, 18, tzinfo=UTC),
            lookback_days=90,
            limit=3,
        ),
        context,
    )

    assert runbooks[0].source_name == "hybrid-knowledge"
    assert runbooks[0].citation.uri.startswith("internal://knowledge/runbooks/")
    assert runbooks[0].service == "payment-service"
    assert incidents[0].metadata["document_type"] == "incident"
    assert incidents[0].citation.uri.startswith("internal://knowledge/incidents/")


@pytest.mark.asyncio
async def test_rag_provider_does_not_block_event_loop_during_sync_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever, _ = build_fixture_retriever(clock=lambda: FIXED_NOW)
    original_search = retriever.search

    def slow_search(request: SearchQuery) -> RetrievalResult:
        time.sleep(0.05)
        return original_search(request)

    monkeypatch.setattr(retriever, "search", slow_search)
    provider = RagKnowledgeProvider(retriever)
    context = QueryContext(
        correlation_id="rag-provider-timeout",
        deadline=datetime(2026, 7, 18, 3, 1, tzinfo=UTC),
        remaining_tool_calls=5,
    )

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            provider.search_runbooks(
                SearchRunbooksInput(
                    service="payment-service",
                    query="database connection pool timeout",
                ),
                context,
            ),
            timeout=0.005,
        )
    await asyncio.sleep(0.06)
