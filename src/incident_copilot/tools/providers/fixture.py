"""Deterministic offline provider backed by a versioned incident fixture."""

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from incident_copilot.domain.common import SourceType
from incident_copilot.domain.evidence import Evidence
from incident_copilot.fixtures.schemas import IncidentFixture
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


class FixtureProvider:
    """Implement every Phase 2 provider port over one immutable fixture."""

    def __init__(self, fixture: IncidentFixture) -> None:
        self._fixture = fixture
        self._evidence = fixture.evidence

    @property
    def fixture(self) -> IncidentFixture:
        """Expose the validated envelope for tests and demo metadata only."""
        return self._fixture

    @classmethod
    def from_path(cls, path: Path) -> "FixtureProvider":
        """Load and fully validate a UTF-8 fixture before serving any query."""
        fixture = IncidentFixture.model_validate_json(path.read_text(encoding="utf-8"))
        return cls(fixture)

    @classmethod
    def payment_service(cls) -> "FixtureProvider":
        """Load the repository's canonical payment-service incident scenario."""
        repository_root = Path(__file__).parents[4]
        return cls.from_path(
            repository_root / "data" / "incidents" / "payment-service-pool-exhaustion.json"
        )

    async def search(self, query: SearchLogsInput, context: QueryContext) -> tuple[Evidence, ...]:
        """Return deterministic log evidence matching service, time, and text."""
        del context
        matches = self._by_source_service(SourceType.LOG, query.service)
        matches = self._within_window(matches, query.start_time, query.end_time)
        if query.query is not None:
            matches = (item for item in matches if self._text_matches(item, query.query))
        return self._ordered(matches)[: query.limit]

    async def query(
        self,
        query: QueryMetricsInput | QueryTracesInput,
        context: QueryContext,
    ) -> tuple[Evidence, ...]:
        """Dispatch the two query-shaped provider ports by validated input type."""
        del context
        if isinstance(query, QueryMetricsInput):
            matches = self._by_source_service(SourceType.METRIC, query.service)
            matches = self._within_window(matches, query.start_time, query.end_time)
            matches = (
                item
                for item in matches
                if item.metadata.get("metric_name") == query.metric_name
                and item.metadata.get("aggregation") == query.aggregation
            )
            return self._ordered(matches)[: query.limit]

        matches = self._by_source_service(SourceType.TRACE, query.service)
        matches = self._within_window(matches, query.start_time, query.end_time)
        if query.operation is not None:
            operation = query.operation.casefold()
            matches = (
                item
                for item in matches
                if str(item.metadata.get("operation", "")).casefold() == operation
            )
        if query.status is not None:
            matches = (item for item in matches if item.metadata.get("status") == query.status)
        return self._ordered(matches)[: query.limit]

    async def recent(
        self, query: GetRecentChangesInput, context: QueryContext
    ) -> tuple[Evidence, ...]:
        """Return newest matching deployment/configuration changes first."""
        del context
        matches = self._by_source_service(SourceType.CHANGE, query.service)
        matches = self._within_window(matches, query.start_time, query.end_time)
        if query.change_type is not None:
            matches = (
                item for item in matches if item.metadata.get("change_type") == query.change_type
            )
        return self._ordered(matches, newest_first=True)[: query.limit]

    async def get(
        self, query: GetServiceTopologyInput, context: QueryContext
    ) -> tuple[Evidence, ...]:
        """Return the latest topology snapshot at or before the requested time."""
        del context
        matches = self._by_source_service(SourceType.TOPOLOGY, query.service)
        matches = (
            item
            for item in matches
            if item.timestamp is not None
            and item.timestamp <= query.at_time
            and self._within_depth(item, query.depth)
        )
        return self._ordered(matches, newest_first=True)[: query.limit]

    async def search_runbooks(
        self, query: SearchRunbooksInput, context: QueryContext
    ) -> tuple[Evidence, ...]:
        """Return fixture knowledge explicitly classified as runbooks."""
        del context
        matches = self._knowledge(query.service, "runbook", query.query)
        return self._ordered(matches, newest_first=True)[: query.limit]

    async def search_similar_incidents(
        self, query: SearchSimilarIncidentsInput, context: QueryContext
    ) -> tuple[Evidence, ...]:
        """Return historical incidents inside the caller's bounded lookback."""
        del context
        earliest = query.before_time - timedelta(days=query.lookback_days)
        matches = self._knowledge(query.service, "incident", query.query)
        matches = (
            item
            for item in matches
            if item.timestamp is not None and earliest <= item.timestamp < query.before_time
        )
        return self._ordered(matches, newest_first=True)[: query.limit]

    def _knowledge(self, service: str, kind: str, query: str) -> Iterable[Evidence]:
        matches = self._by_source_service(SourceType.KNOWLEDGE, service)
        return (
            item
            for item in matches
            if item.metadata.get("knowledge_kind") == kind and self._text_matches(item, query)
        )

    def _by_source_service(self, source_type: SourceType, service: str) -> Iterable[Evidence]:
        return (
            item
            for item in self._evidence
            if item.source_type is source_type and item.service == service
        )

    @staticmethod
    def _within_window(
        evidence: Iterable[Evidence], start_time: datetime, end_time: datetime
    ) -> Iterable[Evidence]:
        return (item for item in evidence if FixtureProvider._overlaps(item, start_time, end_time))

    @staticmethod
    def _overlaps(item: Evidence, start_time: datetime, end_time: datetime) -> bool:
        if item.timestamp is not None:
            return start_time <= item.timestamp <= end_time
        if item.start_time is None or item.end_time is None:
            return False
        return item.start_time <= end_time and item.end_time >= start_time

    @staticmethod
    def _within_depth(item: Evidence, requested_depth: int) -> bool:
        value = item.metadata.get("depth")
        return isinstance(value, int) and not isinstance(value, bool) and value <= requested_depth

    @staticmethod
    def _text_matches(item: Evidence, query: str) -> bool:
        terms = re.findall(r"[a-z0-9_.-]+", query.casefold())
        haystack = " ".join(
            (
                item.title,
                item.summary,
                json.dumps(item.content, sort_keys=True),
                json.dumps(item.metadata, sort_keys=True),
            )
        ).casefold()
        return bool(terms) and all(term in haystack for term in terms)

    @staticmethod
    def _ordered(
        evidence: Iterable[Evidence], *, newest_first: bool = False
    ) -> tuple[Evidence, ...]:
        minimum = datetime.min.replace(tzinfo=UTC)
        return tuple(
            sorted(
                evidence,
                key=lambda item: (item.timestamp or item.start_time or minimum, item.evidence_id),
                reverse=newest_first,
            )
        )
