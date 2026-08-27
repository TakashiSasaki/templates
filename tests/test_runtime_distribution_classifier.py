from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.classify_runtime_distribution_ci import (
    ClassificationError,
    ZERO_SHA,
    changed_paths,
    classify_paths,
    is_compatibility_sensitive_path,
    main,
    write_github_output,
)


def test_compatibility_sensitive_boundary_is_conservative() -> None:
    for path in (
        "scripts/smoke_test_runtime_distribution.py",
        "scripts/future_helper.py",
        "tests/test_future_runtime.py",
        ".github/workflows/runtime-distribution.yml",
        ".github/workflows/future-ci.yml",
        "pyproject.toml",
        "requirements-runtime.lock",
        "release/toolchain.json",
        "skills/agent-policy/SKILL.md",
        "src/agent_policy/cli.py",
        "src/agent_policy/_data/templates/generated.txt",
    ):
        assert is_compatibility_sensitive_path(path), path

    for path in (
        "README.md",
        "docs/maintainer.md",
        "policy/core/testing.md",
        "repository-policy/maintainer-validation.md",
        "translations/ja/README.md",
        ".agent-policy.yml",
        "requirements-ci.lock",
    ):
        assert not is_compatibility_sensitive_path(path), path


def test_unsafe_paths_and_empty_change_sets_fail_closed() -> None:
    for path in ("", "/docs/x.md", "../docs/x.md", "docs/../x.md", "docs\\x.md"):
        assert is_compatibility_sensitive_path(path)
        required, reason = classify_paths([path])
        assert required is True
        assert reason == "compatibility-sensitive-change"

    required, reason = classify_paths([])
    assert required is True
    assert reason == "no-changes"


def test_non_runtime_policy_changes_skip_full_matrix() -> None:
    required, reason = classify_paths(
        [
            "README.md",
            "policy/core/testing.md",
            "repository-policy/maintainer-validation.md",
        ]
    )
    assert required is False
    assert reason == "compatibility-insensitive-change"


def test_mixed_change_with_python_requires_full_matrix() -> None:
    required, reason = classify_paths(
        ["policy/core/testing.md", "scripts/verify_runtime_environment.py"]
    )
    assert required is True
    assert reason == "compatibility-sensitive-change"


@patch("scripts.classify_runtime_distribution_ci.subprocess.run")
def test_git_diff_disables_renames_and_parses_nul_paths(run) -> None:
    base = "1" * 40
    head = "2" * 40
    run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=b"docs/a.md\0scripts/runtime.py\0",
        stderr=b"",
    )
    assert changed_paths(base, head) == ["docs/a.md", "scripts/runtime.py"]
    command = run.call_args.args[0]
    assert command[:2] == ["git", "diff"]
    assert "--no-renames" in command
    assert "-z" in command
    assert command[-3:] == [base, head, "--"]


@patch("scripts.classify_runtime_distribution_ci.subprocess.run")
def test_git_diff_failure_is_explicit(run) -> None:
    run.return_value = subprocess.CompletedProcess(
        args=[], returncode=128, stdout=b"", stderr=b"missing revision"
    )
    try:
        changed_paths("1" * 40, "2" * 40)
    except ClassificationError as exc:
        assert "missing revision" in str(exc)
    else:
        raise AssertionError("expected ClassificationError")


def test_github_output_contains_only_stable_non_path_values() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "output"
        write_github_output(
            output,
            required=False,
            reason="compatibility-insensitive-change",
            count=3,
        )
        assert output.read_text(encoding="utf-8") == (
            "required=false\n"
            "reason=compatibility-insensitive-change\n"
            "changed_count=3\n"
        )


def test_explicit_checkpoint_promotes_insensitive_change() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "output"
        argv = [
            "classify_runtime_distribution_ci.py",
            "--base",
            "1" * 40,
            "--head",
            "2" * 40,
            "--force-compatibility",
            "true",
            "--github-output",
            str(output),
        ]
        with (
            patch.object(sys, "argv", argv),
            patch(
                "scripts.classify_runtime_distribution_ci.changed_paths",
                return_value=["README.md"],
            ),
        ):
            assert main() == 0

        text = output.read_text(encoding="utf-8")
        assert "required=true\n" in text
        assert "reason=explicit-checkpoint\n" in text


def test_zero_sha_is_the_unbounded_push_sentinel() -> None:
    assert ZERO_SHA == "0" * 40
