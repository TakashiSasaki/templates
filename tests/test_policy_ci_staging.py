from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_CI = ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME_CI = ROOT / ".github" / "workflows" / "runtime-distribution.yml"
DOCS = ROOT / "docs" / "staged-ci.md"


def test_policy_ci_has_real_preflight_before_dependent_core_validation() -> None:
    workflow = POLICY_CI.read_text(encoding="utf-8")
    assert "  preflight:\n    name: CI preflight" in workflow
    assert "  core:\n    name: core validation\n    needs:\n      - preflight" in workflow
    assert "name: preflight + core" not in workflow.lower()

    compile_index = workflow.index("- name: Compile Python sources")
    core_index = workflow.index("  core:")
    tests_index = workflow.index("- name: Run tests")
    assert compile_index < core_index < tests_index


def test_policy_ci_routes_applicability_from_preflight_to_conditional_probes() -> None:
    workflow = POLICY_CI.read_text(encoding="utf-8")
    assert (
        "release_state_required: ${{ steps.classify.outputs.release_state_required }}"
        in workflow
    )
    assert (
        "trusted_review_required: ${{ steps.classify.outputs.trusted_review_required }}"
        in workflow
    )
    assert "if: needs.preflight.outputs.release_state_required == 'true'" in workflow
    assert "if: needs.preflight.outputs.trusted_review_required == 'true'" in workflow

    tests_index = workflow.index("- name: Run tests")
    release_index = workflow.index("- name: Verify stable release synchronization")
    review_index = workflow.index("- name: Verify trusted review promotion candidate")
    assert tests_index < release_index < review_index


def test_policy_ci_fails_closed_on_malformed_applicability_outputs() -> None:
    workflow = POLICY_CI.read_text(encoding="utf-8")
    validate_index = workflow.index("- name: Validate Policy CI applicability outputs")
    record_index = workflow.index("- name: Record Policy CI applicability")
    core_index = workflow.index("  core:")

    assert validate_index < record_index < core_index
    assert '"release_state_required=$RELEASE_REQUIRED"' in workflow
    assert '"trusted_review_required=$REVIEW_REQUIRED"' in workflow
    assert 'case "$value" in' in workflow
    assert "true|false)" in workflow
    assert "Malformed Policy CI applicability output" in workflow
    assert "exit 1" in workflow


def test_bootstrap_full_fallback_does_not_execute_proposed_classifier() -> None:
    workflow = POLICY_CI.read_text(encoding="utf-8")
    fallback_start = workflow.index('authority_source="base-unavailable-full"')
    fallback_end = workflow.index("            fi\n", fallback_start)
    fallback = workflow[fallback_start:fallback_end]

    assert 'echo "release_state_required=true"' in fallback
    assert 'echo "trusted_review_required=true"' in fallback
    assert 'echo "overall_reason=full"' in fallback
    assert 'echo "changed_count=unknown"' in fallback
    assert "exit 0" in fallback
    assert "cp scripts/" not in fallback
    assert "classify_policy_ci.py" not in fallback
    assert "force_full=true" not in fallback


def test_policy_ci_preflight_is_cheap_relative_to_core() -> None:
    workflow = POLICY_CI.read_text(encoding="utf-8")
    preflight, core = workflow.split("  core:\n", 1)
    assert "setup-python" not in preflight
    assert "pip install" not in preflight
    assert "pytest" not in preflight
    assert "Compile Python sources" in preflight
    assert "setup-python" in core
    assert "pip install" in core
    assert "pytest" in core


def test_repository_preserves_parallel_full_compatibility_surface() -> None:
    policy = POLICY_CI.read_text(encoding="utf-8")
    runtime = RUNTIME_CI.read_text(encoding="utf-8")
    docs = DOCS.read_text(encoding="utf-8")
    assert "cancel-in-progress: true" in policy
    assert "cancel-in-progress: true" in runtime
    assert "ci/full-compatibility" in runtime
    assert "Policy runtime distribution" in docs
    assert "parallel to normal Policy CI" in docs
