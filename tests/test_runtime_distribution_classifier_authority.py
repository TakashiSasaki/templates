from __future__ import annotations

from pathlib import Path

from scripts import classify_runtime_distribution_ci as runtime_classifier

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
    assert 'echo "compatibility_requested=true"' in fallback
    assert "cp scripts/classify_runtime_distribution_ci.py" not in fallback
    assert "cp scripts/ci_change_classification.py" not in fallback
    assert "classify_runtime_distribution_ci.py\" \\" not in fallback
    assert "force_compatibility=true" not in fallback


def test_runtime_classifier_distinguishes_ci_authority_from_ordinary_sensitive_changes() -> None:
    for path in (
        ".github/workflows/runtime-distribution.yml",
        "scripts/classify_runtime_distribution_ci.py",
        "scripts/ci_change_classification.py",
    ):
        assert runtime_classifier.classify_paths([path]) == (
            True,
            "compatibility-authority-change",
        )

    assert runtime_classifier.classify_paths(["src/agent_policy/cli.py"]) == (
        True,
        "compatibility-sensitive-change",
    )


def test_runtime_fail_closed_and_authority_reasons_force_full_compatibility() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    classification = workflow.split("python3 -I", 1)[1].split(
        "\n\n      - name: Record runtime CI selection", 1
    )[0]

    assert 'reason="$(sed -n \'s/^reason=//p\'' in classification
    assert (
        "compatibility-authority-change|no-changes|unrecognized-path|unsafe-path|"
        "unbounded-push|diff-unavailable)" in classification
    )
    assert "compatibility-sensitive-change)" in classification
    assert "git diff --name-only --no-renames" in classification
    for authority_path in (
        ".github/workflows",
        "scripts/classify_runtime_distribution_ci.py",
        "scripts/ci_change_classification.py",
    ):
        assert authority_path in classification
    assert classification.count('echo "compatibility_requested=true"') >= 3


def test_runtime_classifier_reason_contract_distinguishes_fast_and_full_paths() -> None:
    assert runtime_classifier.classify_paths(["src/agent_policy/cli.py"]) == (
        True,
        "compatibility-sensitive-change",
    )
    assert runtime_classifier.classify_paths(
        [".github/workflows/runtime-distribution.yml"]
    ) == (True, "compatibility-authority-change")
    assert runtime_classifier.classify_paths(["docs\\windows-only-name.md"]) == (
        True,
        "unsafe-path",
    )
    assert runtime_classifier.classify_paths([]) == (True, "no-changes")
    assert runtime_classifier.classify_paths(["unknown_dir/future.json"]) == (
        True,
        "unrecognized-path",
    )


def test_runtime_materialized_classifier_keeps_repository_workspace_binding() -> None:
    classifier = CLASSIFIER.read_text(encoding="utf-8")
    assert 'os.environ.get("GITHUB_WORKSPACE")' in classifier
    assert "Path(_WORKSPACE).resolve()" in classifier
