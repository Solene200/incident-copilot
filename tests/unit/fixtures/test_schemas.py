"""版本化 Fixture 文件测试。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.domain.evidence import CONTENT_HASH_ALGORITHM, content_sha256
from incident_copilot.fixtures import FixtureGroundTruth, IncidentFixture


def test_example_fixture_parses_from_disk() -> None:
    path = Path(__file__).parents[3] / "data" / "incidents" / "example.json"

    fixture = IncidentFixture.model_validate_json(path.read_text(encoding="utf-8"))

    assert fixture.schema_version == "1.0"
    assert fixture.contains_sensitive_data is False
    assert fixture.evidence[0].citation.uri.startswith("fixture://")


def test_fixture_rejects_ground_truth_reference_to_missing_evidence() -> None:
    path = Path(__file__).parents[3] / "data" / "incidents" / "example.json"
    fixture = IncidentFixture.model_validate_json(path.read_text(encoding="utf-8"))
    payload = fixture.model_dump(mode="json")
    payload["ground_truth"] = FixtureGroundTruth(
        root_cause="test-only root cause",
        expected_evidence_ids=["ev_missing"],
    ).model_dump(mode="json")

    with pytest.raises(ValidationError, match="missing from fixture"):
        IncidentFixture.model_validate(payload)


def test_all_fixtures_declare_hash_version_without_handwritten_hashes() -> None:
    incident_root = Path(__file__).parents[3] / "data" / "incidents"

    for path in sorted(incident_root.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["content_hash_algorithm"] == CONTENT_HASH_ALGORITHM
        assert all("content_hash" not in item for item in raw["evidence"])
        assert all("content_hash" not in item["citation"] for item in raw["evidence"])

        fixture = IncidentFixture.model_validate(raw)
        for evidence in fixture.evidence:
            assert evidence.content_hash == content_sha256(evidence.content)
            assert evidence.citation.content_hash == evidence.content_hash
