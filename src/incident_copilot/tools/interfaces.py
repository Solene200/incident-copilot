"""工具层使用的 Provider 端口。"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from incident_copilot.domain.evidence import Evidence
from incident_copilot.tools.schemas import (
    GetRecentChangesInput,
    GetServiceTopologyInput,
    QueryContext,
    QueryMetricsInput,
    QueryTracesInput,
    SearchLogsInput,
    SearchRunbooksInput,
    SearchSimilarIncidentsInput,
)


@runtime_checkable
class LogProvider(Protocol):
    """有界日志证据搜索端口。"""

    async def search(self, query: SearchLogsInput, context: QueryContext) -> Sequence[Evidence]:
        """返回匹配的日志证据或空序列。"""
        ...


@runtime_checkable
class MetricsProvider(Protocol):
    """有界指标证据查询端口。"""

    async def query(self, query: QueryMetricsInput, context: QueryContext) -> Sequence[Evidence]:
        """返回匹配的指标证据或空序列。"""
        ...


@runtime_checkable
class TraceProvider(Protocol):
    """有界分布式 Trace 搜索端口。"""

    async def query(self, query: QueryTracesInput, context: QueryContext) -> Sequence[Evidence]:
        """返回匹配的 Trace 证据或空序列。"""
        ...


@runtime_checkable
class ChangeProvider(Protocol):
    """近期部署和配置变更查询端口。"""

    async def recent(
        self, query: GetRecentChangesInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """返回匹配的变更证据或空序列。"""
        ...


@runtime_checkable
class TopologyProvider(Protocol):
    """指定时间点的服务拓扑证据端口。"""

    async def get(
        self, query: GetServiceTopologyInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """返回匹配的拓扑证据或空序列。"""
        ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    """确定性 Runbook 和历史事故查找使用的 Phase 2 端口。

    Phase 3 可以在不修改工具名称的情况下把该端口适配到混合检索。
    """

    async def search_runbooks(
        self, query: SearchRunbooksInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """返回匹配的 Runbook 证据或空序列。"""
        ...

    async def search_similar_incidents(
        self, query: SearchSimilarIncidentsInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """返回匹配的历史事故证据或空序列。"""
        ...
