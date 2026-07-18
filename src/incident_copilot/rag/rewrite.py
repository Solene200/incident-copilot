"""Fixture 检索使用的透明确定性查询改写。"""

import re
from typing import ClassVar


class QueryRewriter:
    """不调用 LLM,只展开经过审核的小型别名表。"""

    _phrase_expansions: ClassVar[dict[str, str]] = {
        "连接池": "connection pool database",
        "数据库": "database db postgres",
        "超时": "timeout latency",
        "支付服务": "payment-service checkout",
        "历史故障": "historical incident",
    }
    _token_expansions: ClassVar[dict[str, tuple[str, ...]]] = {
        "db": ("database", "postgres"),
        "postgresql": ("postgres", "database"),
        "timeout": ("latency", "timed", "out"),
        "checkout": ("payment-service", "payment"),
        "pool": ("connections", "acquisition"),
    }

    def rewrite(self, query: str) -> str:
        """依次返回规范化原始词和去重后的已审核别名。"""
        normalized = " ".join(query.strip().casefold().split())
        if len(normalized) < 2:
            raise ValueError("query must contain at least two characters")
        terms = re.findall(r"[a-z0-9_.:/-]+|[\u4e00-\u9fff]+", normalized)
        output: list[str] = []

        def append(value: str) -> None:
            if value and value not in output:
                output.append(value)

        for term in terms:
            append(term)
            for expansion in self._token_expansions.get(term, ()):
                append(expansion)
        for phrase, expansion in self._phrase_expansions.items():
            if phrase in normalized:
                for term in expansion.split():
                    append(term)
        return " ".join(output)
