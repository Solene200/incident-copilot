"""Tests for validated knowledge loading and heading-aware splitting."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from incident_copilot.rag.loader import (
    MAX_KNOWLEDGE_FILE_BYTES,
    KnowledgeLoadError,
    MarkdownDocumentLoader,
)
from incident_copilot.rag.schemas import (
    DocumentType,
    KnowledgeDocument,
    content_sha256,
)
from incident_copilot.rag.splitter import MarkdownSplitter, tokenize


def repository_knowledge_root() -> Path:
    return Path(__file__).parents[3] / "data" / "knowledge"


def make_document(content: str, **overrides: object) -> KnowledgeDocument:
    payload: dict[str, object] = {
        "document_id": "doc_test_splitter",
        "document_type": DocumentType.RUNBOOK,
        "title": "Test splitter runbook",
        "source_uri": "internal://knowledge/test-splitter.md",
        "service_tags": ["PAYMENT-SERVICE", "payment-service"],
        "environment_tags": ["Production"],
        "version": "1.0",
        "effective_at": datetime(2026, 7, 1, tzinfo=UTC),
        "ingested_at": datetime(2026, 7, 18, tzinfo=UTC),
        "content": content,
        "content_hash": content_sha256(content),
        "metadata": {"owner": "test"},
    }
    payload.update(overrides)
    return KnowledgeDocument.model_validate(payload)


def write_document(path: Path, *, document_id: str) -> None:
    path.write_text(
        f'''+++
document_id = "{document_id}"
document_type = "runbook"
title = "Temporary runbook"
source_uri = "internal://knowledge/{path.name}"
service_tags = ["payment-service"]
environment_tags = ["production"]
version = "1.0"
effective_at = "2026-07-01T00:00:00Z"
ingested_at = "2026-07-18T00:00:00Z"
metadata = {{ owner = "test" }}
+++
# Diagnosis

Inspect database connection pool saturation.
''',
        encoding="utf-8",
    )


def test_repository_corpus_loads_with_normalized_metadata_and_real_hashes() -> None:
    documents = MarkdownDocumentLoader(repository_knowledge_root()).load()

    assert len(documents) == 6
    assert {document.document_type for document in documents} == {
        DocumentType.RUNBOOK,
        DocumentType.SERVICE,
        DocumentType.INCIDENT,
    }
    assert [document.document_id for document in documents] == sorted(
        document.document_id for document in documents
    )
    for document in documents:
        assert document.content_hash == content_sha256(document.content)
        assert document.source_uri.startswith("internal://knowledge/")
        assert all(service == service.lower() for service in document.service_tags)


@pytest.mark.parametrize(
    "raw_text",
    [
        "# no frontmatter",
        "+++\ndocument_id = [invalid\n+++\nbody",
        '+++\ndocument_id = "doc_unterminated"\nbody',
    ],
)
def test_loader_rejects_missing_invalid_or_unterminated_frontmatter(
    tmp_path: Path, raw_text: str
) -> None:
    (tmp_path / "invalid.md").write_text(raw_text, encoding="utf-8")

    with pytest.raises(KnowledgeLoadError):
        MarkdownDocumentLoader(tmp_path).load()


def test_loader_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    write_document(tmp_path / "first.md", document_id="doc_duplicate")
    write_document(tmp_path / "second.md", document_id="doc_duplicate")

    with pytest.raises(KnowledgeLoadError, match="duplicate knowledge document_id"):
        MarkdownDocumentLoader(tmp_path).load()


def test_loader_rejects_oversized_document_before_reading_content(tmp_path: Path) -> None:
    (tmp_path / "oversized.md").write_text(
        "x" * (MAX_KNOWLEDGE_FILE_BYTES + 1),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError, match="size limit"):
        MarkdownDocumentLoader(tmp_path).load()


def test_splitter_preserves_heading_metadata_hash_and_citation() -> None:
    document = make_document(
        """# Symptoms

Connection acquisition times out.

# Diagnosis

Inspect database pool utilization and recent configuration changes.
"""
    )

    chunks = MarkdownSplitter(max_tokens=30, overlap_tokens=5).split(document)

    assert [chunk.section_path for chunk in chunks] == [("Symptoms",), ("Diagnosis",)]
    assert [chunk.ordinal for chunk in chunks] == [0, 1]
    assert all(chunk.service_tags == ("payment-service",) for chunk in chunks)
    assert all(chunk.environment_tags == ("production",) for chunk in chunks)
    assert all(chunk.metadata == {"owner": "test"} for chunk in chunks)
    assert all(chunk.content_hash == content_sha256(chunk.text) for chunk in chunks)
    assert all(chunk.citation.content_hash == chunk.content_hash for chunk in chunks)
    assert all(chunk.citation.uri == document.source_uri for chunk in chunks)
    assert all("section=" in chunk.citation.locator for chunk in chunks)


def test_splitter_is_deterministic_bounded_and_overlaps_only_within_section() -> None:
    first_section = " ".join(f"alpha{i}" for i in range(55))
    second_section = " ".join(f"beta{i}" for i in range(10))
    document = make_document(
        f"# Long section\n\n{first_section}\n\n# Separate section\n\n{second_section}"
    )
    splitter = MarkdownSplitter(max_tokens=24, overlap_tokens=4)

    first = splitter.split(document)
    second = splitter.split(document)

    assert first == second
    assert len(first) >= 4
    assert all(chunk.token_count <= 24 for chunk in first)
    long_chunks = [chunk for chunk in first if chunk.section_path == ("Long section",)]
    separate_chunks = [chunk for chunk in first if chunk.section_path == ("Separate section",)]
    assert len(long_chunks) >= 2
    assert len(separate_chunks) == 1
    previous_tokens = set(tokenize(long_chunks[0].text))
    next_tokens = set(tokenize(long_chunks[1].text))
    assert previous_tokens.intersection(next_tokens)
    assert "alpha" not in separate_chunks[0].text


def test_splitter_enforces_token_bound_for_cjk_without_whitespace() -> None:
    content = "# 长段落\n\n" + "数据库连接池超时" * 100
    document = make_document(content)

    chunks = MarkdownSplitter(max_tokens=20, overlap_tokens=2).split(document)

    assert len(chunks) > 1
    assert all(chunk.token_count <= 20 for chunk in chunks)


def test_split_documents_orders_by_document_id() -> None:
    later = make_document("# Section\n\nlater body", document_id="doc_z_later", title="Later")
    earlier = make_document(
        "# Section\n\nearlier body", document_id="doc_a_earlier", title="Earlier"
    )

    chunks = MarkdownSplitter().split_documents((later, earlier))

    assert [chunk.document_id for chunk in chunks] == ["doc_a_earlier", "doc_z_later"]
