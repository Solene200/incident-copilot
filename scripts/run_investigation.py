"""Run the complete offline payment-service investigation and print its report."""

import asyncio
import json

from incident_copilot.graph import build_offline_investigation_graph, create_initial_state
from incident_copilot.tools.providers.fixture import FixtureProvider


async def main() -> None:
    """Execute the no-key Fixture/RAG/Fake-Model graph once."""
    incident = FixtureProvider.payment_service().fixture.incident
    graph = build_offline_investigation_graph()
    state = await graph.ainvoke(create_initial_state(incident))
    report = state["final_report"]
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
