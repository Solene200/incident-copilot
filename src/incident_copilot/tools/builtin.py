"""Composition of the seven Phase 2 read-only tools."""

from collections.abc import Sequence
from dataclasses import dataclass

from incident_copilot.domain.common import SourceType
from incident_copilot.domain.evidence import Evidence
from incident_copilot.tools.interfaces import (
    ChangeProvider,
    KnowledgeProvider,
    LogProvider,
    MetricsProvider,
    TopologyProvider,
    TraceProvider,
)
from incident_copilot.tools.registry import ToolDefinition, ToolRegistry
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


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    """Explicit dependency injection for every Phase 2 provider port."""

    logs: LogProvider
    metrics: MetricsProvider
    traces: TraceProvider
    changes: ChangeProvider
    topology: TopologyProvider
    knowledge: KnowledgeProvider


def build_tool_registry(
    providers: ProviderBundle,
    *,
    timeout_seconds: float = 2.0,
    max_retries: int = 1,
    retry_backoff_seconds: float = 0.01,
) -> ToolRegistry:
    """Register all seven tools against injected providers."""
    registry = ToolRegistry(retry_backoff_seconds=retry_backoff_seconds)

    async def search_logs(query: SearchLogsInput, context: QueryContext) -> Sequence[Evidence]:
        return await providers.logs.search(query, context)

    async def query_metrics(query: QueryMetricsInput, context: QueryContext) -> Sequence[Evidence]:
        return await providers.metrics.query(query, context)

    async def query_traces(query: QueryTracesInput, context: QueryContext) -> Sequence[Evidence]:
        return await providers.traces.query(query, context)

    async def get_service_topology(
        query: GetServiceTopologyInput, context: QueryContext
    ) -> Sequence[Evidence]:
        return await providers.topology.get(query, context)

    async def get_recent_changes(
        query: GetRecentChangesInput, context: QueryContext
    ) -> Sequence[Evidence]:
        return await providers.changes.recent(query, context)

    async def search_runbooks(
        query: SearchRunbooksInput, context: QueryContext
    ) -> Sequence[Evidence]:
        return await providers.knowledge.search_runbooks(query, context)

    async def search_similar_incidents(
        query: SearchSimilarIncidentsInput, context: QueryContext
    ) -> Sequence[Evidence]:
        return await providers.knowledge.search_similar_incidents(query, context)

    registry.register(
        ToolDefinition(
            "search_logs",
            SearchLogsInput,
            search_logs,
            frozenset({SourceType.LOG}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "query_metrics",
            QueryMetricsInput,
            query_metrics,
            frozenset({SourceType.METRIC}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "query_traces",
            QueryTracesInput,
            query_traces,
            frozenset({SourceType.TRACE}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "get_service_topology",
            GetServiceTopologyInput,
            get_service_topology,
            frozenset({SourceType.TOPOLOGY}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "get_recent_changes",
            GetRecentChangesInput,
            get_recent_changes,
            frozenset({SourceType.CHANGE}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "search_runbooks",
            SearchRunbooksInput,
            search_runbooks,
            frozenset({SourceType.KNOWLEDGE}),
            timeout_seconds,
            max_retries,
        )
    )
    registry.register(
        ToolDefinition(
            "search_similar_incidents",
            SearchSimilarIncidentsInput,
            search_similar_incidents,
            frozenset({SourceType.KNOWLEDGE}),
            timeout_seconds,
            max_retries,
        )
    )
    return registry
