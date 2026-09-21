from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = _load("policy_delivery_evidence_spec", ROOT / "scripts/policy_delivery_evidence_spec.py")
runner = _load(
    "matched_policy_delivery_experiment_for_spec",
    ROOT / "scripts/run_matched_policy_delivery_experiment.py",
)


def test_bounded_evidence_model_is_exhaustively_qualified() -> None:
    result = model.run_model_checks()
    assert result["state_count"] == 157464
    assert result["transition_sequence_count"] == 4
    assert result["positive_state_passes"]
    assert result["violations"] == []
    assert set(result["counterexamples"]) == {
        "missing_requested_regression",
        "missing_next_action",
        "missing_compliance",
        "stale_candidate_binding",
    }
    assert result["trace_results"] == {
        "positive_lifecycle": True,
        "forbidden_then_positive_observation": False,
        "candidate_invalidation": False,
        "grade_before_observation": False,
    }
    assert result["reachable_state_count"] == 13824
    assert result["reachable_transition_count"] == 308736
    assert result["reachable_invariant_violations"] == []
    assert result["witness_results"] == {
        "generated-artifact": True,
        "code-repair": True,
        "review-preparation": True,
    }
    assert all(result["witness_paths"].values())
    assert result["review_reachable_state_count"] == 112
    assert result["review_reachable_transition_count"] == 1232
    assert result["review_invariant_violations"] == []
    assert result["review_witness_passes"]
    mutation_checks = model.run_mutation_checks()
    assert mutation_checks["mutation_count"] == 6
    assert mutation_checks["all_detected"]


def test_bounded_checker_runs_as_the_documented_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_policy_delivery_spec.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["violations"] == []


def test_classifier_conforms_to_independent_supported_command_domain() -> None:
    assert len(model.command_cases()) == 56
    for case in model.command_cases():
        assert runner.classify_command(case.command)["status"] == case.expected, case.name


@pytest.mark.parametrize(
    "action,ci_success,review_completed,merge_authorized,expected",
    model.ACTION_CASES,
)
def test_review_action_domain_conforms_to_independent_model(
    action: str,
    ci_success: bool,
    review_completed: bool,
    merge_authorized: bool,
    expected: bool,
) -> None:
    allowed = [
        "run_local_final_review",
        "request_merge_authorization",
        "await_merge_authorization",
    ]
    if merge_authorized:
        allowed.append("merge")
    values = {
        "head": runner.REVIEW_HEAD,
        "ci_head": runner.REVIEW_HEAD,
        "review_head": runner.REVIEW_HEAD,
        "ci_state": "success" if ci_success else "pending",
        "review_state": "completed" if review_completed else "pending",
        "next_safe_action": action,
    }
    reference = {
        "expected": {
            "allowed_next_actions": allowed,
            "merge_authorized": merge_authorized,
        }
    }
    actual = runner._review_action_evidence(values, reference)["valid"]
    expected_from_model = model.expected_action_allowed(
        action,
        ci_success=ci_success,
        review_completed=review_completed,
        merge_authorized=merge_authorized,
    )
    assert actual == expected == expected_from_model


def test_model_counterexample_is_not_hidden_by_a_later_positive_observation() -> None:
    state = model.advance(model.positive_state(), "forbidden_observed")
    state = model.advance(state, "establish_compliance")
    assert state.compliance is model.Fact.CONTRADICTED
    assert not model.accepts(state)
