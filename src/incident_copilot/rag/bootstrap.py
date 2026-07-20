"""确定性仓库知识语料的组合辅助函数。"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from incident_copilot.rag.bm25 import BM25Index
from incident_copilot.rag.embeddings import FakeEmbedding
from incident_copilot.rag.loader import MarkdownDocumentLoader
from incident_copilot.rag.retrieval import HybridRetriever
from incident_copilot.rag.rewrite import QueryRewriter
from incident_copilot.rag.schemas import IngestResult
from incident_copilot.rag.splitter import MarkdownSplitter
from incident_copilot.rag.vector_store import InMemoryVectorStore


def repository_knowledge_root() -> Path:
    """解析版本化知识语料位置,但不依赖当前工作目录。"""
    return Path(__file__).parents[3] / "data" / "knowledge"


def build_fixture_retriever(
    *,
    knowledge_root: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[HybridRetriever, IngestResult]:
    """使用确定性组件构造完整离线 RAG 管线并摄取知识。"""
    embedding = FakeEmbedding(dimension=64)
    retriever = HybridRetriever(
        splitter=MarkdownSplitter(),
        embedding=embedding,
        lexical_index=BM25Index(),
        vector_store=InMemoryVectorStore(dimension=embedding.dimension),
        rewriter=QueryRewriter(),
        clock=clock,
    )
    documents = MarkdownDocumentLoader(knowledge_root or repository_knowledge_root()).load()
    result = retriever.ingest(documents)
    return retriever, result
