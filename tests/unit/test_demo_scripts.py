"""Tests for deterministic transformations used by the real-source demo."""

from datetime import UTC, datetime, timedelta

from incident_copilot.demo import shift_fixture_to_now
from incident_copilot.tools.providers import FixtureProvider


def test_live_demo_shift_preserves_relative_times_and_citation_integrity() -> None:
    original = FixtureProvider.payment_service().fixture
    reference_end = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    shifted = shift_fixture_to_now(original, reference_end)

    assert shifted.incident.end_time == reference_end
    assert shifted.incident.end_time - shifted.incident.start_time == timedelta(minutes=20)
    assert shifted.incident.incident_id.startswith("inc_payment_live_")
    assert [item.evidence_id for item in shifted.evidence] == [
        item.evidence_id for item in original.evidence
    ]
    for before, after in zip(original.evidence, shifted.evidence, strict=True):
        assert before.content_hash == after.content_hash
        assert after.citation.content_hash == after.content_hash
        if before.timestamp is not None:
            assert after.timestamp is not None
            assert after.timestamp - before.timestamp == (
                reference_end - original.incident.end_time
            )
