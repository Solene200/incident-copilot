"""全部七个 Fixture 工具的端到端契约测试。"""

from datetime import UTC, datetime, timedelta

import pytest

from incident_copilot.domain.common import SourceType
from incident_copilot.tools import (
    FixtureProvider,
    ProviderBundle,
    QueryContext,
    build_tool_registry,
)
from incident_copilot.tools.registry import ToolRegistry


def make_registry() -> ToolRegistry:
    provider = FixtureProvider.payment_service()
    return build_tool_registry(
        ProviderBundle(
            logs=provider,
            metrics=provider,
            traces=provider,
            changes=provider,
            topology=provider,
            knowledge=provider,
        ),
        retry_backoff_seconds=0,
    )


def make_context() -> QueryContext:
    return QueryContext(
        correlation_id="integration-seven-tools",
        deadline=datetime.now(UTC) + timedelta(seconds=5),
        remaining_tool_attempts=20,
    )


CASES: tuple[tuple[str, dict[str, object], SourceType, str], ...] = (
    (
        "search_logs",
        {
            "service": "payment-service",
            "start_time": "2026-07-18T10:20:00+08:00",
            "end_time": "2026-07-18T10:40:00+08:00",
            "query": "connection acquisition",
        },
        SourceType.LOG,
        "ev_payment_log_pool_timeout",
    ),
    (
        "query_metrics",
        {
            "service": "payment-service",
            "start_time": "2026-07-18T10:20:00+08:00",
            "end_time": "2026-07-18T10:40:00+08:00",
            "metric_name": "db.pool.utilization",
            "aggregation": "max",
        },
        SourceType.METRIC,
        "ev_payment_metric_pool_saturation",
    ),
    (
        "query_traces",
        {
            "service": "payment-service",
            "start_time": "2026-07-18T10:20:00+08:00",
            "end_time": "2026-07-18T10:40:00+08:00",
            "operation": "POST /payments",
            "status": "timeout",
        },
        SourceType.TRACE,
        "ev_payment_trace_db_wait",
    ),
    (
        "get_service_topology",
        {
            "service": "payment-service",
            "at_time": "2026-07-18T10:30:00+08:00",
            "depth": 1,
        },
        SourceType.TOPOLOGY,
        "ev_payment_topology_dependencies",
    ),
    (
        "get_recent_changes",
        {
            "service": "payment-service",
            "start_time": "2026-07-18T10:00:00+08:00",
            "end_time": "2026-07-18T10:40:00+08:00",
            "change_type": "configuration",
        },
        SourceType.CHANGE,
        "ev_payment_change_pool_limit",
    ),
    (
        "search_runbooks",
        {"service": "payment-service", "query": "connection pool timeout"},
        SourceType.KNOWLEDGE,
        "ev_payment_runbook_pool_timeout",
    ),
    (
        "search_similar_incidents",
        {
            "service": "payment-service",
            "query": "connection pool timeout",
            "before_time": "2026-07-18T10:00:00+08:00",
            "lookback_days": 90,
        },
        SourceType.KNOWLEDGE,
        "ev_payment_incident_similar_pool",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "source_type", "evidence_id"), CASES)
async def test_each_fixture_tool_returns_citable_evidence(
    tool_name: str,
    arguments: dict[str, object],
    source_type: SourceType,
    evidence_id: str,
) -> None:
    registry = make_registry()

    result = await registry.execute(tool_name, arguments, make_context())

    assert result.tool_name == tool_name
    assert result.attempts == 1
    assert [item.evidence_id for item in result.evidence] == [evidence_id]
    evidence = result.evidence[0]
    assert evidence.source_type is source_type
    assert evidence.source_name.startswith("fixture-")
    assert evidence.service is not None
    assert evidence.timestamp is not None or evidence.start_time is not None
    assert evidence.citation.uri.startswith("fixture://")


@pytest.mark.asyncio
async def test_fixture_tool_returns_honest_empty_result() -> None:
    result = await make_registry().execute(
        "search_logs",
        {
            "service": "payment-service",
            "start_time": "2026-07-18T10:20:00+08:00",
            "end_time": "2026-07-18T10:40:00+08:00",
            "query": "kafka rebalance",
        },
        make_context(),
    )

    assert result.evidence == ()
    assert result.attempts == 1
