"""Version and path safety tests for the checked-in evaluation dataset."""

import pytest
from pydantic import ValidationError

from incident_copilot.evaluation.dataset import load_evaluation_dataset
from incident_copilot.evaluation.schemas import EvaluationSample


def test_default_dataset_contains_distinct_known_root_cause_samples() -> None:
    dataset = load_evaluation_dataset()

    assert dataset.version == "1.0.0"
    assert len(dataset.samples) == 3
    assert len({sample.ground_truth.failure_type for sample in dataset.samples}) == 3
    assert all(sample.ground_truth.root_cause_terms for sample in dataset.samples)


def test_dataset_rejects_fixture_path_traversal() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        EvaluationSample.model_validate(
            {
                "sample_id": "eval_escape",
                "fixture_path": "../secret.json",
                "retrieval_query": "bounded query",
                "ground_truth": {
                    "affected_services": ["payment-service"],
                    "failure_type": "test_failure",
                    "root_cause_terms": ["cause"],
                },
            }
        )
