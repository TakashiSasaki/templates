from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_policy_preflight.py"


def load_preflight():
    spec = importlib.util.spec_from_file_location("policy_ready_preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ready_profile_requires_a_base_ref_and_has_an_explicit_profile() -> None:
    preflight = load_preflight()
    assert preflight.parse_args(["ready", "--base-ref", "a" * 40]).profile == "ready"
    assert preflight.parse_args(["ready", "--base-ref", "a" * 40]).base_ref == "a" * 40


def test_ready_runs_release_and_trusted_checks_selected_by_shared_classifier() -> None:
    preflight = load_preflight()
    calls: list[str] = []
    decision = SimpleNamespace(
        release_state_required=True,
        trusted_review_required=False,
    )
    with patch.object(preflight, "require_clean_tree"), patch.object(
        preflight, "classify_ready_applicability", return_value=decision
    ), patch.dict(
        preflight.CHECKS,
        {name: (lambda name=name: calls.append(name)) for name in preflight.CHECKS},
    ):
        selected = preflight.run_ready("a" * 40, "b" * 40)
    assert "release-state" in selected
    assert "trusted-review" not in selected
    assert calls[-1] == "release-state"


def test_classifier_uncertainty_fails_closed_to_both_expensive_probes() -> None:
    preflight = load_preflight()
    with patch(
        "scripts.classify_policy_ci.changed_paths",
        side_effect=RuntimeError("base unavailable"),
    ):
        decision = preflight.classify_ready_applicability("a" * 40, "b" * 40)
    assert decision.release_state_required is True
    assert decision.trusted_review_required is True
    assert decision.overall_reason == "full"


def test_malformed_or_unknown_classifier_results_fail_closed() -> None:
    preflight = load_preflight()
    for result in (
        object(),
        SimpleNamespace(
            release_state_required=None,
            trusted_review_required=False,
        ),
    ):
        with patch("scripts.classify_policy_ci.classify_paths", return_value=result):
            decision = preflight.classify_ready_applicability("a" * 40, "b" * 40)
        assert decision.release_state_required is True
        assert decision.trusted_review_required is True
