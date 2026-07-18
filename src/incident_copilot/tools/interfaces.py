"""Provider ports consumed by the tool layer."""

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
    """Port for bounded log evidence searches."""

    async def search(self, query: SearchLogsInput, context: QueryContext) -> Sequence[Evidence]:
        """Return matching log evidence or an empty sequence."""
        ...


@runtime_checkable
class MetricsProvider(Protocol):
    """Port for bounded metric evidence queries."""

    async def query(self, query: QueryMetricsInput, context: QueryContext) -> Sequence[Evidence]:
        """Return matching metric evidence or an empty sequence."""
        ...


@runtime_checkable
class TraceProvider(Protocol):
    """Port for bounded distributed trace searches."""

    async def query(self, query: QueryTracesInput, context: QueryContext) -> Sequence[Evidence]:
        """Return matching trace evidence or an empty sequence."""
        ...


@runtime_checkable
class ChangeProvider(Protocol):
    """Port for recent deployment and configuration changes."""

    async def recent(
        self, query: GetRecentChangesInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """Return matching change evidence or an empty sequence."""
        ...


@runtime_checkable
class TopologyProvider(Protocol):
    """Port for point-in-time service topology evidence."""

    async def get(
        self, query: GetServiceTopologyInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """Return matching topology evidence or an empty sequence."""
        ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Phase 2 port for deterministic runbook and incident lookup.

    Phase 3 may adapt this port to hybrid retrieval without changing tool names.
    """

    async def search_runbooks(
        self, query: SearchRunbooksInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """Return matching runbook evidence or an empty sequence."""
        ...

    async def search_similar_incidents(
        self, query: SearchSimilarIncidentsInput, context: QueryContext
    ) -> Sequence[Evidence]:
        """Return matching historical incident evidence or an empty sequence."""
        ...
