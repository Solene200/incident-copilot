"""确定性多数据源 Fixture Provider 契约测试。"""

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from incident_copilot.domain.common import SourceType
from incident_copilot.tools.interfaces import (
    ChangeProvider,
    KnowledgeProvider,
    LogProvider,
    MetricsProvider,
    TopologyProvider,
    TraceProvider,
)
from incident_copilot.tools.providers import FixtureProvider
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

FIXTURE_TIMEZONE = timezone(timedelta(hours=8))
WINDOW_START = datetime(2026, 7, 18, 10, 0, tzinfo=FIXTURE_TIMEZONE)
WINDOW_END = datetime(2026, 7, 18, 10, 40, tzinfo=FIXTURE_TIMEZONE)


def make_context() -> QueryContext:
    return QueryContext(
        correlation_id="test-fixture-provider",
        deadline=datetime.now(UTC) + timedelta(seconds=5),
        remaining_tool_calls=10,
    )


def test_fixture_implements_all_provider_protocols_and_is_internally_consistent() -> None:
    provider = FixtureProvider.payment_service()

    assert isinstance(provider, LogProvider)
    assert isinstance(provider, MetricsProvider)
    assert isinstance(provider, TraceProvider)
    assert isinstance(provider, ChangeProvider)
    assert isinstance(provider, TopologyProvider)
    assert isinstance(provider, KnowledgeProvider)
    assert len(provider.fixture.evidence) == 12
    assert provider.fixture.ground_truth is not None
    assert provider.fixture.ground_truth.affected_services == ("payment-service",)

    for evidence in provider.fixture.evidence:
        assert evidence.source_name.startswith("fixture-")
        assert evidence.service is not None
        assert evidence.timestamp is not None or evidence.start_time is not None
        assert evidence.citation.uri.endswith("payment-service-pool-exhaustion.json")
        assert evidence.citation.content_hash == evidence.content_hash
        canonical_content = json.dumps(
            evidence.content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        assert hashlib.sha256(canonical_content).hexdigest() == evidence.content_hash


@pytest.mark.asyncio
async def test_fixture_provider_returns_each_source_with_expected_filters() -> None:
    provider = FixtureProvider.payment_service()
    context = make_context()

    logs = await provider.search(
        SearchLogsInput(
            service="PAYMENT-SERVICE",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            query="connection acquisition",
        ),
        context,
    )
    metrics = await provider.query(
        QueryMetricsInput(
            service="payment-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            metric_name="db.pool.utilization",
            aggregation="max",
        ),
        context,
    )
    traces = await provider.query(
        QueryTracesInput(
            service="payment-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            operation="POST /payments",
            status="timeout",
        ),
        context,
    )
    changes = await provider.recent(
        GetRecentChangesInput(
            service="payment-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            change_type="configuration",
        ),
        context,
    )
    topology = await provider.get(
        GetServiceTopologyInput(
            service="payment-service",
            at_time=WINDOW_END,
            depth=1,
        ),
        context,
    )
    runbooks = await provider.search_runbooks(
        SearchRunbooksInput(
            service="payment-service",
            query="connection pool timeout",
        ),
        context,
    )
    incidents = await provider.search_similar_incidents(
        SearchSimilarIncidentsInput(
            service="payment-service",
            query="connection pool timeout",
            before_time=WINDOW_START,
            lookback_days=90,
        ),
        context,
    )

    assert [item.evidence_id for item in logs] == ["ev_payment_log_pool_timeout"]
    assert [item.evidence_id for item in metrics] == ["ev_payment_metric_pool_saturation"]
    assert [item.evidence_id for item in traces] == ["ev_payment_trace_db_wait"]
    assert [item.evidence_id for item in changes] == ["ev_payment_change_pool_limit"]
    assert [item.evidence_id for item in topology] == ["ev_payment_topology_dependencies"]
    assert [item.evidence_id for item in runbooks] == ["ev_payment_runbook_pool_timeout"]
    assert [item.evidence_id for item in incidents] == ["ev_payment_incident_similar_pool"]


@pytest.mark.asyncio
async def test_fixture_provider_empty_result_and_limit_are_deterministic() -> None:
    provider = FixtureProvider.payment_service()
    context = make_context()

    empty = await provider.search(
        SearchLogsInput(
            service="payment-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            query="kafka rebalance",
        ),
        context,
    )
    limited = await provider.search(
        SearchLogsInput(
            service="payment-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            limit=1,
        ),
        context,
    )
    gateway = await provider.query(
        QueryMetricsInput(
            service="payment-gateway",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            metric_name="dependency.gateway.latency",
            aggregation="p95",
        ),
        context,
    )
    empty_metrics = await provider.query(
        QueryMetricsInput(
            service="unknown-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
            metric_name="db.pool.utilization",
        ),
        context,
    )
    empty_traces = await provider.query(
        QueryTracesInput(
            service="unknown-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
        ),
        context,
    )
    empty_changes = await provider.recent(
        GetRecentChangesInput(
            service="unknown-service",
            start_time=WINDOW_START,
            end_time=WINDOW_END,
        ),
        context,
    )
    empty_topology = await provider.get(
        GetServiceTopologyInput(service="unknown-service", at_time=WINDOW_END),
        context,
    )
    empty_runbooks = await provider.search_runbooks(
        SearchRunbooksInput(service="unknown-service", query="connection pool"),
        context,
    )
    empty_incidents = await provider.search_similar_incidents(
        SearchSimilarIncidentsInput(
            service="unknown-service",
            query="connection pool",
            before_time=WINDOW_START,
        ),
        context,
    )

    assert empty == ()
    assert [item.evidence_id for item in limited] == ["ev_payment_log_pool_timeout"]
    assert gateway[0].metadata["contradicts_gateway_root_cause"] is True
    assert gateway[0].source_type is SourceType.METRIC
    assert (
        empty_metrics
        == empty_traces
        == empty_changes
        == empty_topology
        == empty_runbooks
        == empty_incidents
        == ()
    )
