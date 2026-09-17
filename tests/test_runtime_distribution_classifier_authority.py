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


def test_runtime_missing_base_classifier_authority_fails_closed_independently() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fallback = workflow.split('authority_source="base-unavailable-full"', 1)[1].split(
        "exit 0", 1
    )[0]

    assert 'echo "required=true"' in fallback
    assert 'echo "reason=base-classifier-unavailable"' in fallback
    assert 'echo "changed_count=unknown"' in fallback
    assert 'echo "compatibility_requested=true"' not in fallback
    assert "cp scripts/classify_runtime_distribution_ci.py" not in fallback
    assert "cp scripts/ci_change_classification.py" not in fallback
    assert "classify_runtime_distribution_ci.py\" \\" not in fallback
    assert "force_compatibility=true" not in fallback


def test_runtime_classifier_distinguishes_ci_authority_from_ordinary_sensitive_changes() -> None:
    for path in (
        ".github/workflows/runtime-distribution.yml",
        "scripts/classify_runtime_distribution_ci.py",
        "scripts/ci_change_classification.py",
        "scripts/run_policy_runtime_checks.py",
    ):
        assert runtime_classifier.classify_paths([path]) == (
            True,
            "compatibility-authority-change",
        )

    assert runtime_classifier.classify_paths(["src/agent_policy/cli.py"]) == (
        True,
        "compatibility-sensitive-change",
    )


def test_runtime_only_explicit_fast_path_reasons_skip_full_compatibility() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "runtime distribution selection" in workflow
    assert "compatibility_requested" not in workflow
    assert "--force-compatibility" not in workflow


def test_runtime_classifier_reason_contract_distinguishes_runtime_paths() -> None:
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


def test_runtime_workflow_has_no_environment_compatibility_matrix() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "strategy:" not in workflow
    assert "matrix:" not in workflow
    assert "windows-" not in workflow
    assert "python-version" not in workflow
