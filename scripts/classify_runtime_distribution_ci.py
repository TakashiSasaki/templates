#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

if __package__:
    from . import ci_change_classification as common
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ci_change_classification as common  # noqa: E402

DESCRIPTION = "Classify whether Policy requires the full runtime compatibility matrix."
_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
REPOSITORY_ROOT = (
    Path(_WORKSPACE).resolve()
    if _WORKSPACE
    else Path(__file__).resolve().parents[1]
)
ZERO_SHA = common.ZERO_SHA
FULL_SHA = common.FULL_SHA
ClassificationError = common.ClassificationError
validate_sha = common.validate_sha
is_safe_repository_path = common.is_safe_repository_path
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


def is_compatibility_sensitive_path(path: str) -> bool:
    """Return whether one path can affect Policy runtime portability."""
    if not is_safe_repository_path(path):
        return True
    if path.endswith(".py"):
        return True
    if path in COMPATIBILITY_SENSITIVE_FILES:
        return True
    return any(path.startswith(prefix) for prefix in COMPATIBILITY_SENSITIVE_PREFIXES)


def classify_paths(paths: list[str]) -> tuple[bool, str]:
    if not paths:
        return True, "no-changes"
    for path in paths:
        if is_compatibility_sensitive_path(path):
            return True, "compatibility-sensitive-change"
    return False, "compatibility-insensitive-change"


def changed_paths(base: str, head: str) -> list[str]:
    return common.changed_paths(
        REPOSITORY_ROOT,
        base,
        head,
        runner=subprocess.run,
    )


def write_github_output(path: Path, *, required: bool, reason: str, count: int) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"required={'true' if required else 'false'}\n")
        output.write(f"reason={reason}\n")
        output.write(f"changed_count={count}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
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
