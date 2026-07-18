"""End-to-end Phase 6 evaluation over Fixture, RAG, Fake Model, and LangGraph."""

import json
import socket
from pathlib import Path

import pytest

from incident_copilot.evaluation import OfflineEvaluationRunner, load_evaluation_dataset
from incident_copilot.evaluation.schemas import EvaluationDataset


@pytest.mark.asyncio
async def test_offline_evaluation_writes_raw_and_summary_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_network(self: socket.socket, address: object) -> None:
        del self, address
        raise AssertionError("offline evaluation attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    dataset = load_evaluation_dataset()

    summary = await OfflineEvaluationRunner().run(dataset, tmp_path)

    assert summary.sample_count == 3
    assert summary.completed_sample_count == 3
    assert summary.failed_sample_count == 0
    assert summary.metrics.token_usage_estimated is True
    assert summary.metrics.estimated_cost_usd is None
    raw_lines = (tmp_path / "raw-results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 3
    raw = [json.loads(line) for line in raw_lines]
    assert {item["sample_id"] for item in raw} == {
        "eval_payment_pool_exhaustion",
        "eval_checkout_dns_misconfiguration",
        "eval_inventory_cache_regression",
    }
    assert all(item["report"] is not None for item in raw)
    assert all(item["usage"]["token_usage_estimated"] is True for item in raw)
    assert (tmp_path / "summary.json").is_file()
    assert (tmp_path / "summary.md").is_file()


@pytest.mark.asyncio
async def test_failed_sample_is_retained_in_raw_results_and_denominator(tmp_path: Path) -> None:
    original = load_evaluation_dataset()
    missing = original.samples[0].model_copy(
        update={"fixture_path": "data/incidents/does-not-exist.json"}
    )
    dataset = EvaluationDataset(
        dataset_id="dataset_failure_retention",
        version="1.0.0",
        description="One deliberately unavailable fixture for runner failure retention.",
        samples=(missing,),
    )

    summary = await OfflineEvaluationRunner().run(dataset, tmp_path)

    assert summary.sample_count == 1
    assert summary.completed_sample_count == 0
    assert summary.failed_sample_count == 1
    raw = json.loads((tmp_path / "raw-results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert raw["status"] == "failed"
    assert raw["error"].startswith("FileNotFoundError:")
    assert summary.metrics.root_cause_accuracy is None
    assert summary.metrics.total_tokens == 0
