"""Pure, exhaustively tested investigation loop routing policy."""

from dataclasses import dataclass
from typing import Literal

from incident_copilot.graph.schemas import RouteTarget, StopReason
from incident_copilot.graph.state import InvestigationState


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """A route target coupled to its auditable reason when research stops."""

    target: RouteTarget
    stop_reason: StopReason | None


def decide_after_judge(state: InvestigationState) -> RouteDecision:
    """Apply non-model stop rules in fixed priority order."""
    if state.get("deadline_exceeded", False):
        return RouteDecision(RouteTarget.REPORT, StopReason.DEADLINE_EXCEEDED)
    if state.get("tool_call_count", 0) >= state["max_tool_calls"]:
        return RouteDecision(RouteTarget.REPORT, StopReason.TOOL_BUDGET_EXHAUSTED)
    if state.get("model_call_count", 0) >= state["max_model_calls"]:
        return RouteDecision(RouteTarget.REPORT, StopReason.MODEL_BUDGET_EXHAUSTED)
    if state.get("evidence_sufficient", False):
        return RouteDecision(RouteTarget.REPORT, StopReason.EVIDENCE_SUFFICIENT)
    if state["research_round"] >= state["max_research_rounds"]:
        return RouteDecision(RouteTarget.REPORT, StopReason.MAX_RESEARCH_ROUNDS)
    return RouteDecision(RouteTarget.REFINE, None)


def route_after_judge(
    state: InvestigationState,
) -> Literal["refine_investigation", "generate_report"]:
    """Return only a predeclared graph node name."""
    if decide_after_judge(state).target is RouteTarget.REFINE:
        return "refine_investigation"
    return "generate_report"
