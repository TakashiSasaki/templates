#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

ZERO_SHA = "0" * 40
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
RunCommand = Callable[..., subprocess.CompletedProcess[bytes]]

POLICY_CI_CONTROL_PATHS = frozenset(
    {
        ".github/workflows/ci.yml",
        "scripts/ci_change_classification.py",
        "scripts/classify_policy_ci.py",
    }
)
POLICY_CI_CONTROL_PREFIXES = ("tests/fixtures/ci-applicability/",)


class ClassificationError(RuntimeError):
    """Raised when a Git diff cannot be classified safely."""


def is_safe_repository_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    return all(part not in {"", ".", ".."} for part in path.split("/"))


def policy_ci_control_change_requires_full(paths: list[str]) -> bool:
    """Return whether Policy CI classification controls changed.

    Keep this guard outside ``classify_policy_ci.py`` so a change to that classifier
    cannot redefine whether its own change requires full verification.
    """
    return any(
        path in POLICY_CI_CONTROL_PATHS
        or any(path.startswith(prefix) for prefix in POLICY_CI_CONTROL_PREFIXES)
        for path in paths
    )


def validate_sha(value: str, label: str) -> None:
    if not FULL_SHA.fullmatch(value):
        raise ClassificationError(f"{label} must be a full lowercase Git SHA")


def changed_paths(
    repository_root: Path,
    base: str,
    head: str,
    *,
    runner: RunCommand = subprocess.run,
) -> list[str]:
    """Return changed paths, treating renames as delete+add."""
    validate_sha(base, "base")
    validate_sha(head, "head")
    result = runner(
        [
            "git",
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            base,
            head,
            "--",
        ],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ClassificationError(f"git diff failed: {stderr or result.returncode}")
    try:
        decoded = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClassificationError("git diff returned a non-UTF-8 path") from exc
    return [path for path in decoded.split("\0") if path]
