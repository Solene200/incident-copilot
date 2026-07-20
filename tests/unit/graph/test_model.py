"""离线结构化模型契约测试。"""

from datetime import UTC, datetime

import pytest

from incident_copilot.graph.model import FakeModelProvider
from incident_copilot.graph.schemas import ModelContext, ModelTask, PlanOutput


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_query", "symptoms", "expected_log", "expected_metric", "expected_operation", "count"),
    [
        (
            "requests have database connection acquisition timeouts",
            (),
            "connection acquisition",
            "db.pool.utilization",
            "POST /payments",
            7,
        ),
        (
            "requests fail after a resolver rollout",
            ("DNS lookup timeout",),
            "DNS lookup timeout",
            "http.server.error_rate",
            "GET /payment",
            6,
        ),
        (
            "latency increased after cache TTL rollout",
            ("cache miss surge",),
            "cache miss",
            "process.cpu.utilization",
            "GET /payment",
            6,
        ),
    ],
)
async def test_fake_model_returns_scenario_specific_schema_valid_plans(
    raw_query: str,
    symptoms: tuple[str, ...],
    expected_log: str,
    expected_metric: str,
    expected_operation: str,
    count: int,
) -> None:
    context = ModelContext(
        task=ModelTask.PLAN,
        incident_id="inc_test",
        service="payment-service",
        raw_query=raw_query,
        symptoms=symptoms,
        start_time=datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
        end_time=datetime(2026, 7, 18, 2, 40, tzinfo=UTC),
        research_round=1,
    )

    response = await FakeModelProvider().complete(context)
    output = PlanOutput.model_validate(response.payload)

    by_tool = {step.tool_name: step for step in output.steps}
    assert len(output.steps) == count
    assert len({step.query_key for step in output.steps}) == count
    assert by_tool["search_logs"].arguments["query"] == expected_log
    assert by_tool["query_metrics"].arguments["metric_name"] == expected_metric
    assert by_tool["query_traces"].arguments["operation"] == expected_operation
    assert response.usage.estimated is True


@pytest.mark.asyncio
async def test_fake_planner_does_not_use_incident_identity() -> None:
    base = ModelContext(
        task=ModelTask.PLAN,
        incident_id="inc_first_identity",
        service="checkout-service",
        raw_query="resolver rollout caused failures",
        symptoms=("DNS lookup timeout",),
        start_time=datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
        end_time=datetime(2026, 7, 18, 2, 40, tzinfo=UTC),
        research_round=1,
    )
    renamed = base.model_copy(update={"incident_id": "inc_unrelated_identity"})

    first = PlanOutput.model_validate((await FakeModelProvider().complete(base)).payload)
    second = PlanOutput.model_validate((await FakeModelProvider().complete(renamed)).payload)

    assert first == second
