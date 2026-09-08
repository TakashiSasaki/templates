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
        'authority_source="proposed-head-fallback-full"',
        'force_full=true',
        '"$classifier_dir/classify_policy_ci.py"',
        "classifier authority",
    ):
        assert fragment in workflow

    assert "python3 -I scripts/classify_policy_ci.py" not in workflow


def test_materialized_classifier_keeps_repository_workspace_binding() -> None:
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    assert 'os.environ.get("GITHUB_WORKSPACE")' in classifier
    assert "Path(_WORKSPACE).resolve()" in classifier


def test_missing_base_classifier_authority_fails_closed_to_full() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fallback_index = workflow.index('authority_source="proposed-head-fallback-full"')
    force_index = workflow.rfind("force_full=true", 0, fallback_index)
    assert force_index >= 0
