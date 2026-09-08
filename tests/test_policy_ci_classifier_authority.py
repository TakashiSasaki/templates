from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CLASSIFIER = ROOT / "scripts" / "classify_policy_ci.py"


def test_pull_request_classifier_authority_comes_from_base_revision() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for fragment in (
        'git show "$BASE_SHA:scripts/classify_policy_ci.py"',
        'git show "$BASE_SHA:scripts/ci_change_classification.py"',
        'authority_source="base"',
        '"$classifier_dir/classify_policy_ci.py"',
        "classifier authority",
    ):
        assert fragment in workflow

    assert "python3 -I scripts/classify_policy_ci.py" not in workflow


def test_materialized_classifier_keeps_repository_workspace_binding() -> None:
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    assert 'os.environ.get("GITHUB_WORKSPACE")' in classifier
    assert "Path(_WORKSPACE).resolve()" in classifier


def test_missing_base_classifier_authority_forces_full_without_proposed_code() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fallback_start = workflow.index('authority_source="base-unavailable-full"')
    fallback_end = workflow.index("            fi\n", fallback_start)
    fallback = workflow[fallback_start:fallback_end]

    for fragment in (
        'echo "release_state_required=true"',
        'echo "release_state_reason=base-classifier-unavailable"',
        'echo "trusted_review_required=true"',
        'echo "trusted_review_reason=base-classifier-unavailable"',
        'echo "overall_reason=full"',
        'echo "changed_count=unknown"',
        "exit 0",
    ):
        assert fragment in fallback

    assert "cp scripts/" not in fallback
    assert "classify_policy_ci.py" not in fallback
    assert "force_full=true" not in fallback
