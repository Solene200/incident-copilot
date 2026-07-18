"""Deterministic helpers used only by the portfolio demonstration."""

from datetime import datetime

from incident_copilot.domain.evidence import Evidence
from incident_copilot.fixtures.schemas import IncidentFixture


def shift_fixture_to_now(fixture: IncidentFixture, reference_end: datetime) -> IncidentFixture:
    """Move fixture envelope times to a live metric window without changing evidence claims."""
    delta = reference_end - fixture.incident.end_time

    def shifted(value: datetime | None) -> datetime | None:
        return value + delta if value is not None else None

    evidence: list[Evidence] = []
    for item in fixture.evidence:
        evidence.append(
            item.model_copy(
                update={
                    "timestamp": shifted(item.timestamp),
                    "start_time": shifted(item.start_time),
                    "end_time": shifted(item.end_time),
                    "collected_at": shifted(item.collected_at),
                    "citation": item.citation.model_copy(
                        update={"retrieved_at": shifted(item.citation.retrieved_at)}
                    ),
                }
            )
        )
    incident = fixture.incident.model_copy(
        update={
            "incident_id": f"inc_payment_live_{reference_end.strftime('%Y%m%d_%H%M%S')}",
            "start_time": fixture.incident.start_time + delta,
            "end_time": reference_end,
            "created_at": reference_end,
        }
    )
    return fixture.model_copy(update={"incident": incident, "evidence": tuple(evidence)})
