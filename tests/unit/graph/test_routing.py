"""非模型调查停止策略的真值表测试。"""

import pytest

from incident_copilot.graph.routing import decide_after_judge
from incident_copilot.graph.schemas import ModelUsage, RouteTarget, StopReason
from incident_copilot.graph.state import InvestigationState


def base_state() -> InvestigationState:
    return InvestigationState(
        research_round=1,
        max_research_rounds=2,
        tool_call_count=2,
        max_tool_calls=10,
        tool_attempt_count=3,
        max_tool_attempts=20,
        model_call_count=2,
        max_model_calls=10,
        model_usage=ModelUsage(input_tokens=10, output_tokens=10),
        max_estimated_tokens=1_000,
        evidence_sufficient=False,
        deadline_exceeded=False,
    )


@pytest.mark.parametrize(
    ("updates", "reason"),
    (
        ({"deadline_exceeded": True}, StopReason.DEADLINE_EXCEEDED),
        ({"tool_call_count": 10}, StopReason.TOOL_BUDGET_EXHAUSTED),
        ({"tool_attempt_count": 20}, StopReason.TOOL_BUDGET_EXHAUSTED),
        ({"model_call_count": 10}, StopReason.MODEL_BUDGET_EXHAUSTED),
        (
            {"model_usage": ModelUsage(input_tokens=600, output_tokens=400)},
            StopReason.TOKEN_BUDGET_EXHAUSTED,
        ),
        ({"evidence_sufficient": True}, StopReason.EVIDENCE_SUFFICIENT),
        ({"research_round": 2}, StopReason.MAX_RESEARCH_ROUNDS),
    ),
)
def test_stop_routes(updates: dict[str, object], reason: StopReason) -> None:
    state = base_state()
    state.update(updates)  # type: ignore[typeddict-item]

    decision = decide_after_judge(state)

    assert decision.target is RouteTarget.REPORT
    assert decision.stop_reason is reason


def test_route_refines_only_when_all_budgets_allow_it() -> None:
    decision = decide_after_judge(base_state())

    assert decision.target is RouteTarget.REFINE
    assert decision.stop_reason is None


def test_deadline_has_priority_over_other_stop_reasons() -> None:
    state = base_state()
    state["deadline_exceeded"] = True
    state["tool_call_count"] = state["max_tool_calls"]
    state["evidence_sufficient"] = True

    assert decide_after_judge(state).stop_reason is StopReason.DEADLINE_EXCEEDED
