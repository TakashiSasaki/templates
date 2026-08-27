#!/usr/bin/env python3
"""Classify whether Policy requires the full runtime compatibility matrix."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ZERO_SHA = "0" * 40
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
COMPATIBILITY_SENSITIVE_PREFIXES = (
    ".github/workflows/",
    "release/",
    "skills/agent-policy/",
    "src/",
)
COMPATIBILITY_SENSITIVE_FILES = frozenset(
    {
        "pyproject.toml",
        "requirements-runtime.lock",
    }
)


class ClassificationError(RuntimeError):
    """Raised when a Git diff cannot be classified safely."""


def is_safe_repository_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    return all(part not in {"", ".", ".."} for part in path.split("/"))


def is_compatibility_sensitive_path(path: str) -> bool:
    """Return whether one path can affect Policy runtime portability."""
    if not is_safe_repository_path(path):
        return True
    if path.endswith(".py"):
        return True
    if path in COMPATIBILITY_SENSITIVE_FILES:
        return True
    return any(path.startswith(prefix) for prefix in COMPATIBILITY_SENSITIVE_PREFIXES)


def classify_paths(paths: Sequence[str]) -> tuple[bool, str]:
    """Return (compatibility_required, stable_reason) for one changed-path set."""
    if not paths:
        return True, "no-changes"
    for path in paths:
        if is_compatibility_sensitive_path(path):
            return True, "compatibility-sensitive-change"
    return False, "compatibility-insensitive-change"


def validate_sha(value: str, label: str) -> None:
    if not FULL_SHA.fullmatch(value):
        raise ClassificationError(f"{label} must be a full lowercase Git SHA")


def changed_paths(base: str, head: str) -> list[str]:
    """Return all paths changed from base to head, treating renames as delete+add."""
    validate_sha(base, "base")
    validate_sha(head, "head")
    result = subprocess.run(
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
        cwd=REPOSITORY_ROOT,
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


def write_github_output(path: Path, *, required: bool, reason: str, count: int) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"required={'true' if required else 'false'}\n")
        output.write(f"reason={reason}\n")
        output.write(f"changed_count={count}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument(
        "--force-compatibility",
        choices=("true", "false"),
        default="false",
        help="Force the full matrix for an explicit compatibility checkpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    force_compatibility = args.force_compatibility == "true"

    if args.base == ZERO_SHA:
        required, reason, paths = True, "unbounded-push", []
    else:
        try:
            paths = changed_paths(args.base, args.head)
            required, reason = classify_paths(paths)
        except ClassificationError as exc:
            print(
                f"Policy runtime CI classification fell back to required: {exc}",
                file=sys.stderr,
            )
            required, reason, paths = True, "diff-unavailable", []

    if force_compatibility and not required:
        required = True
        reason = "explicit-checkpoint"

    print(
        f"policy-runtime-ci required={str(required).lower()} reason={reason} "
        f"changed_count={len(paths)}"
    )
    for path in paths:
        print(f"changed: {path!r}")
    write_github_output(
        args.github_output,
        required=required,
        reason=reason,
        count=len(paths),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
