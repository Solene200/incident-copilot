"""Heading-aware deterministic Markdown chunking with bounded overlap."""

import re
from dataclasses import dataclass

from incident_copilot.domain.evidence import Citation
from incident_copilot.rag.schemas import (
    KnowledgeChunk,
    KnowledgeDocument,
    content_sha256,
    normalize_document_text,
)

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.:/-]+|[\u4e00-\u9fff]")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def tokenize(value: str) -> tuple[str, ...]:
    """Tokenize English identifiers and individual CJK characters deterministically."""
    return tuple(match.group(0).casefold() for match in TOKEN_PATTERN.finditer(value))


@dataclass(frozen=True, slots=True)
class _Section:
    path: tuple[str, ...]
    body: str


class MarkdownSplitter:
    """Split within Markdown sections and retain citation/metadata lineage."""

    def __init__(self, *, max_tokens: int = 120, overlap_tokens: int = 20) -> None:
        if max_tokens < 20 or max_tokens > 2_000:
            raise ValueError("max_tokens must be between 20 and 2000")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens // 2:
            raise ValueError("overlap_tokens must be non-negative and less than half max_tokens")
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

    def split_documents(
        self, documents: tuple[KnowledgeDocument, ...]
    ) -> tuple[KnowledgeChunk, ...]:
        """Split a stable document sequence into globally stable chunk order."""
        chunks: list[KnowledgeChunk] = []
        for document in sorted(documents, key=lambda item: item.document_id):
            chunks.extend(self.split(document))
        return tuple(chunks)

    def split(self, document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        """Split one document without crossing explicit Markdown heading boundaries."""
        chunk_texts: list[tuple[tuple[str, ...], str]] = []
        for section in self._sections(document):
            for text in self._split_section(section):
                chunk_texts.append((section.path, text))

        chunks: list[KnowledgeChunk] = []
        for ordinal, (section_path, text) in enumerate(chunk_texts):
            content_hash = content_sha256(text)
            stable_suffix = (
                f"{document.document_id.removeprefix('doc_')}_{ordinal}_{content_hash[:12]}"
            )
            chunk_id = f"chunk_{stable_suffix}"
            citation = Citation(
                citation_id=f"cit_{stable_suffix}",
                uri=document.source_uri,
                locator=f"section={' > '.join(section_path)};chunk={ordinal}",
                display_name=f"{document.title} — {' > '.join(section_path)}",
                retrieved_at=document.ingested_at,
                content_hash=content_hash,
            )
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    document_type=document.document_type,
                    document_title=document.title,
                    ordinal=ordinal,
                    text=text,
                    token_count=len(tokenize(text)),
                    section_path=section_path,
                    service_tags=document.service_tags,
                    environment_tags=document.environment_tags,
                    version=document.version,
                    effective_at=document.effective_at,
                    metadata=document.metadata,
                    content_hash=content_hash,
                    citation=citation,
                )
            )
        return tuple(chunks)

    @staticmethod
    def _sections(document: KnowledgeDocument) -> tuple[_Section, ...]:
        heading_stack: list[str] = []
        current_path: tuple[str, ...] = (document.title,)
        body_lines: list[str] = []
        sections: list[_Section] = []

        def flush() -> None:
            body = "\n".join(body_lines).strip()
            if body:
                sections.append(_Section(current_path, body))

        for line in document.content.split("\n"):
            heading = HEADING_PATTERN.match(line)
            if heading is None:
                body_lines.append(line)
                continue
            flush()
            body_lines.clear()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack[level - 1 :] = [title]
            current_path = tuple(heading_stack)
        flush()
        return tuple(sections)

    def _split_section(self, section: _Section) -> tuple[str, ...]:
        prefix = f"Section: {' > '.join(section.path)}"
        prefix_tokens = len(tokenize(prefix))
        available = self._max_tokens - prefix_tokens
        if available < 5:
            raise ValueError("section path leaves no room for chunk content")

        body_words = section.body.split()
        if len(tokenize(section.body)) <= available:
            return (normalize_document_text(f"{prefix}\n{section.body}"),)

        step = available - self._overlap_tokens
        chunks: list[str] = []
        start = 0
        while start < len(body_words):
            end = min(start + available, len(body_words))
            body = " ".join(body_words[start:end])
            chunks.append(normalize_document_text(f"{prefix}\n{body}"))
            if end == len(body_words):
                break
            start += step
        return tuple(chunks)
