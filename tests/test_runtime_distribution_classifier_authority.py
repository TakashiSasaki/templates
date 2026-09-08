from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "runtime-distribution.yml"
CLASSIFIER = ROOT / "scripts" / "classify_runtime_distribution_ci.py"


def test_runtime_pull_request_classifier_authority_comes_from_base_revision() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for fragment in (
        'git show "$BASE_SHA:scripts/classify_runtime_distribution_ci.py"',
        'git show "$BASE_SHA:scripts/ci_change_classification.py"',
        'authority_source="base"',
        'authority_source="base-unavailable-full"',
        '"$classifier_dir/classify_runtime_distribution_ci.py"',
        "authority_source: ${{ steps.classify.outputs.authority_source }}",
    ):
        assert fragment in workflow

    assert "python3 -I scripts/classify_runtime_distribution_ci.py" not in workflow


def test_runtime_missing_base_classifier_authority_forces_full_independently() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fallback = workflow.split('authority_source="base-unavailable-full"', 1)[1].split(
        "exit 0", 1
    )[0]

    assert 'echo "required=true"' in fallback
    assert 'echo "reason=base-classifier-unavailable"' in fallback
    assert 'echo "changed_count=unknown"' in fallback
    assert "cp scripts/classify_runtime_distribution_ci.py" not in fallback
    assert "cp scripts/ci_change_classification.py" not in fallback
    assert "classify_runtime_distribution_ci.py\" \\" not in fallback
    assert "force_compatibility=true" not in fallback


def test_runtime_materialized_classifier_keeps_repository_workspace_binding() -> None:
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    assert 'os.environ.get("GITHUB_WORKSPACE")' in classifier
    assert "Path(_WORKSPACE).resolve()" in classifier
