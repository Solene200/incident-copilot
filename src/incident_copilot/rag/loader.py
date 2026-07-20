"""安全加载带 TOML Frontmatter 的仓库知识文档。"""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from incident_copilot.rag.schemas import KnowledgeDocument, content_sha256

# 知识 Markdown 中 TOML 元数据的开始和结束分隔符。
FRONTMATTER_DELIMITER = "+++"
# 单份知识文档允许读取的最大字节数。
MAX_KNOWLEDGE_FILE_BYTES = 1_000_000


class KnowledgeLoadError(ValueError):
    """知识源无法解析为经过校验的文档契约。"""


class MarkdownDocumentLoader:
    """只加载指定根目录内的 UTF-8 Markdown 文件。"""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def load(self) -> tuple[KnowledgeDocument, ...]:
        """加载顺序稳定的语料,并拒绝重复文档 ID。"""
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
        if path.stat().st_size > MAX_KNOWLEDGE_FILE_BYTES:
            raise KnowledgeLoadError(f"knowledge document exceeds size limit: {path}")
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
