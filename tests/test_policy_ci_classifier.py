from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import scripts.ci_change_classification as common
import scripts.classify_policy_ci as policy_ci

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "ci-applicability" / "cases.json"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
POLICY = ROOT / "policy" / "pull-request" / "exact-head-ci-evidence.md"
DOCS = ROOT / "docs" / "revision-bound-qualification.md"


def test_policy_ci_applicability_scenarios() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 9
    for case in cases:
        decision = policy_ci.classify_paths(case["paths"])
        assert decision.release_state_required is case["release_state_required"], case["name"]
        assert decision.trusted_review_required is case["trusted_review_required"], case["name"]


def test_unknown_or_unsafe_classification_fails_closed() -> None:
    decision = policy_ci.classify_paths([])
    assert decision.release_state_required is True
    assert decision.trusted_review_required is True
    assert decision.overall_reason == "full"

    for path in ("", "/docs/x.md", "../docs/x.md", "docs/../x.md", "docs\\x.md"):
        decision = policy_ci.classify_paths([path])
        assert decision.release_state_required is True
        assert decision.trusted_review_required is True
        assert decision.overall_reason == "full"


def test_explicit_full_checkpoint_overrides_selective_classification() -> None:
    decision = policy_ci.classify_paths(
        ["tests/test_unrelated_behavior.py"],
        force_full=True,
    )
    assert decision.release_state_required is True
    assert decision.trusted_review_required is True
    assert decision.release_state_reason == "explicit-checkpoint"
    assert decision.trusted_review_reason == "explicit-checkpoint"


def test_shared_layer_protects_policy_classifier_control_changes() -> None:
    for path in (
        ".github/workflows/ci.yml",
        "scripts/classify_policy_ci.py",
        "scripts/ci_change_classification.py",
        "tests/fixtures/ci-applicability/cases.json",
    ):
        assert common.policy_ci_control_change_requires_full([path])
        decision = policy_ci.classify_paths([path])
        assert decision.release_state_required is True
        assert decision.trusted_review_required is True
        assert decision.overall_reason == "full"
        assert decision.release_state_reason == "classification-control-change"
        assert decision.trusted_review_reason == "classification-control-change"


def test_shared_diff_classifier_preserves_fail_closed_path_and_sha_rules() -> None:
    for path in ("docs/a.md", "policy/core/testing.md"):
        assert common.is_safe_repository_path(path)
    for path in ("", "/a", "../a", "a/../b", "a\\b"):
        assert not common.is_safe_repository_path(path)

    try:
        common.validate_sha("not-a-sha", "head")
    except common.ClassificationError:
        pass
    else:
        raise AssertionError("expected invalid SHA to fail closed")


def test_policy_classifier_github_output_is_stable_and_non_path_bearing() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "output"
        decision = policy_ci.classify_paths(["policy/core/testing.md"])
        policy_ci.write_github_output(output, decision, count=1)
        text = output.read_text(encoding="utf-8")
        assert "release_state_required=false\n" in text
        assert "trusted_review_required=true\n" in text
        assert "changed_count=1\n" in text
        assert "policy/core/testing.md" not in text


def test_classifiers_remain_executable_under_isolated_python() -> None:
    for script in (
        ROOT / "scripts" / "classify_policy_ci.py",
        ROOT / "scripts" / "classify_runtime_distribution_ci.py",
    ):
        result = subprocess.run(
            [sys.executable, "-I", str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_policy_ci_avoids_duplicate_feature_branch_push_runs() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "push:\n    branches: [policy]" in workflow
    assert "pull_request:" in workflow


def test_policy_ci_records_and_uses_applicability_decisions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "Classify Policy CI verification",
        "scripts/classify_policy_ci.py",
        "Record Policy CI applicability",
        "needs.preflight.outputs.release_state_required == 'true'",
        "needs.preflight.outputs.trusted_review_required == 'true'",
    ):
        assert fragment in workflow


def test_canonical_policy_distinguishes_not_applicable_from_passed() -> None:
    policy = POLICY.read_text(encoding="utf-8").lower()
    docs = DOCS.read_text(encoding="utf-8").lower()
    for fragment in (
        "not-applicable is applicability evidence, not a passing check result",
        "fail closed",
        "classifier",
        "exact relevant revision",
        "explicit full-verification override",
        "must not suppress repository-required automatic checks",
    ):
        assert fragment in policy
    assert "applicability classification" in docs
    assert "diagnostic" in docs
    assert "qualification" in docs
