from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import scripts.classify_runtime_distribution_ci as runtime_ci


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
        assert runtime_ci.is_compatibility_sensitive_path(path), path

    for path in (
        "README.md",
        "docs/maintainer.md",
        "policy/core/testing.md",
        "repository-policy/maintainer-validation.md",
        "translations/ja/README.md",
        ".agent-policy.yml",
        "requirements-ci.lock",
    ):
        assert not runtime_ci.is_compatibility_sensitive_path(path), path


def test_unsafe_paths_and_empty_change_sets_fail_closed() -> None:
    for path in ("", "/docs/x.md", "../docs/x.md", "docs/../x.md", "docs\\x.md"):
        assert runtime_ci.is_compatibility_sensitive_path(path)
        required, reason = runtime_ci.classify_paths([path])
        assert required is True
        assert reason == "compatibility-sensitive-change"

    required, reason = runtime_ci.classify_paths([])
    assert required is True
    assert reason == "no-changes"


def test_non_runtime_policy_changes_skip_full_matrix() -> None:
    required, reason = runtime_ci.classify_paths(
        [
            "README.md",
            "policy/core/testing.md",
            "repository-policy/maintainer-validation.md",
        ]
    )
    assert required is False
    assert reason == "compatibility-insensitive-change"


def test_mixed_change_with_python_requires_full_matrix() -> None:
    required, reason = runtime_ci.classify_paths(
        ["policy/core/testing.md", "scripts/verify_runtime_environment.py"]
    )
    assert required is True
    assert reason == "compatibility-sensitive-change"


def test_git_diff_disables_renames_and_parses_nul_paths(monkeypatch) -> None:
    base = "1" * 40
    head = "2" * 40
    observed: list[list[str]] = []

    def fake_run(command, **kwargs):
        observed.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=b"docs/a.md\0scripts/runtime.py\0",
            stderr=b"",
        )

    monkeypatch.setattr(runtime_ci.subprocess, "run", fake_run)
    assert runtime_ci.changed_paths(base, head) == ["docs/a.md", "scripts/runtime.py"]
    command = observed[0]
    assert command[:2] == ["git", "diff"]
    assert "--no-renames" in command
    assert "-z" in command
    assert command[-3:] == [base, head, "--"]


def test_git_diff_failure_is_explicit(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            args=command,
            returncode=128,
            stdout=b"",
            stderr=b"missing revision",
        )

    monkeypatch.setattr(runtime_ci.subprocess, "run", fake_run)
    try:
        runtime_ci.changed_paths("1" * 40, "2" * 40)
    except runtime_ci.ClassificationError as exc:
        assert "missing revision" in str(exc)
    else:
        raise AssertionError("expected ClassificationError")


def test_github_output_contains_only_stable_non_path_values() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "output"
        runtime_ci.write_github_output(
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


def test_explicit_checkpoint_promotes_insensitive_change(monkeypatch) -> None:
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
        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(runtime_ci, "changed_paths", lambda base, head: ["README.md"])
        assert runtime_ci.main() == 0

        text = output.read_text(encoding="utf-8")
        assert "required=true\n" in text
        assert "reason=explicit-checkpoint\n" in text


def test_zero_sha_is_the_unbounded_push_sentinel() -> None:
    assert runtime_ci.ZERO_SHA == "0" * 40
