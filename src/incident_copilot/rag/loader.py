"""Safe loader for repository knowledge documents with TOML frontmatter."""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from incident_copilot.rag.schemas import KnowledgeDocument, content_sha256

FRONTMATTER_DELIMITER = "+++"


class KnowledgeLoadError(ValueError):
    """A knowledge source could not be parsed into the validated document contract."""


class MarkdownDocumentLoader:
    """Load only UTF-8 Markdown files contained by one configured root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def load(self) -> tuple[KnowledgeDocument, ...]:
        """Load a stable ordered corpus and reject duplicate document IDs."""
        if not self._root.is_dir():
            raise KnowledgeLoadError(f"knowledge directory does not exist: {self._root}")

        documents: list[KnowledgeDocument] = []
        seen_ids: set[str] = set()
        for path in sorted(self._root.rglob("*.md")):
            resolved = path.resolve()
            if not resolved.is_relative_to(self._root):
                raise KnowledgeLoadError(f"knowledge path escapes configured root: {path}")
            document = self._load_file(resolved)
            if document.document_id in seen_ids:
                raise KnowledgeLoadError(f"duplicate knowledge document_id: {document.document_id}")
            seen_ids.add(document.document_id)
            documents.append(document)
        return tuple(documents)

    @staticmethod
    def _load_file(path: Path) -> KnowledgeDocument:
        raw_text = path.read_text(encoding="utf-8")
        lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
            raise KnowledgeLoadError(f"missing TOML frontmatter: {path}")
        try:
            closing_index = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == FRONTMATTER_DELIMITER
            )
        except StopIteration as exc:
            raise KnowledgeLoadError(f"unterminated TOML frontmatter: {path}") from exc

        try:
            metadata: dict[str, Any] = tomllib.loads("\n".join(lines[1:closing_index]))
        except tomllib.TOMLDecodeError as exc:
            raise KnowledgeLoadError(f"invalid TOML frontmatter: {path}") from exc

        content = "\n".join(lines[closing_index + 1 :])
        payload = {
            **metadata,
            "content": content,
            "content_hash": content_sha256(content),
        }
        try:
            return KnowledgeDocument.model_validate(payload)
        except ValidationError as exc:
            raise KnowledgeLoadError(f"invalid knowledge document metadata: {path}") from exc
