#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from . import ci_change_classification as common
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ci_change_classification as common  # noqa: E402

DESCRIPTION = "Classify applicability of expensive Policy CI verification."
_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
REPOSITORY_ROOT = (
    Path(_WORKSPACE).resolve() if _WORKSPACE else Path(__file__).resolve().parents[1]
)
ZERO_SHA = common.ZERO_SHA
ClassificationError = common.ClassificationError

RELEASE_STATE_PREFIXES = (
    "release/",
    "schemas/",
    "src/agent_policy/",
    "skills/agent-policy/",
    "templates/",
)
RELEASE_STATE_FILES = frozenset(
    {
        "action.yml",
        "pyproject.toml",
        "requirements-ci.lock",
        "requirements-runtime.lock",
        "scripts/verify-release-state.py",
    }
)
TRUSTED_REVIEW_PREFIXES = (
    "policy/",
    "profiles/",
    "repository-policy/",
    "release/",
    "schemas/",
    "skills/",
    "src/",
    "templates/",
)
TRUSTED_REVIEW_FILES = frozenset(
    {
        ".agent-policy.yml",
        ".gitattributes",
        "action.yml",
        "pyproject.toml",
        "requirements-ci.lock",
        "requirements-runtime.lock",
        "scripts/verify_trusted_review_candidate.py",
    }
)
RECOGNIZED_UNAFFECTED_PREFIXES = (
    "docs/",
    "tests/",
    "translations/",
)
RECOGNIZED_UNAFFECTED_FILES = frozenset(
    {
        ".gitignore",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
    }
)


@dataclass(frozen=True)
class Decision:
    release_state_required: bool
    release_state_reason: str
    trusted_review_required: bool
    trusted_review_reason: str
    overall_reason: str


def _matches(path: str, *, prefixes: tuple[str, ...], files: frozenset[str]) -> bool:
    return path in files or any(path.startswith(prefix) for prefix in prefixes)


def _is_recognized(path: str) -> bool:
    return (
        _matches(path, prefixes=RELEASE_STATE_PREFIXES, files=RELEASE_STATE_FILES)
        or _matches(path, prefixes=TRUSTED_REVIEW_PREFIXES, files=TRUSTED_REVIEW_FILES)
        or _matches(
            path,
            prefixes=RECOGNIZED_UNAFFECTED_PREFIXES,
            files=RECOGNIZED_UNAFFECTED_FILES,
        )
        or path in common.POLICY_CI_CONTROL_PATHS
        or any(path.startswith(prefix) for prefix in common.POLICY_CI_CONTROL_PREFIXES)
    )


def classify_paths(paths: list[str], *, force_full: bool = False) -> Decision:
    if force_full:
        return Decision(True, "explicit-checkpoint", True, "explicit-checkpoint", "full")
    if not paths:
        return Decision(True, "no-changes", True, "no-changes", "full")
    if any(not common.is_safe_repository_path(path) for path in paths):
        return Decision(True, "unsafe-path", True, "unsafe-path", "full")
    if common.policy_ci_control_change_requires_full(paths):
        return Decision(
            True,
            "classification-control-change",
            True,
            "classification-control-change",
            "full",
        )
    if any(not _is_recognized(path) for path in paths):
        return Decision(
            True,
            "unrecognized-path",
            True,
            "unrecognized-path",
            "full",
        )

    release_required = any(
        _matches(path, prefixes=RELEASE_STATE_PREFIXES, files=RELEASE_STATE_FILES)
        for path in paths
    )
    trusted_required = any(
        _matches(path, prefixes=TRUSTED_REVIEW_PREFIXES, files=TRUSTED_REVIEW_FILES)
        for path in paths
    )
    return Decision(
        release_required,
        "relevant-change" if release_required else "unaffected",
        trusted_required,
        "relevant-change" if trusted_required else "unaffected",
        "selective",
    )


def changed_paths(base: str, head: str) -> list[str]:
    return common.changed_paths(REPOSITORY_ROOT, base, head)


def write_github_output(path: Path, decision: Decision, *, count: int) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(
            "release_state_required="
            f"{'true' if decision.release_state_required else 'false'}\n"
        )
        output.write(f"release_state_reason={decision.release_state_reason}\n")
        output.write(
            "trusted_review_required="
            f"{'true' if decision.trusted_review_required else 'false'}\n"
        )
        output.write(f"trusted_review_reason={decision.trusted_review_reason}\n")
        output.write(f"overall_reason={decision.overall_reason}\n")
        output.write(f"changed_count={count}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument(
        "--force-full",
        choices=("true", "false"),
        default="false",
        help="Force every classified verification for an explicit qualification checkpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    force_full = args.force_full == "true"

    if args.base == ZERO_SHA:
        paths: list[str] = []
        decision = Decision(
            True,
            "unbounded-push",
            True,
            "unbounded-push",
            "full",
        )
    else:
        try:
            paths = changed_paths(args.base, args.head)
            decision = classify_paths(paths, force_full=force_full)
        except ClassificationError as exc:
            print(
                f"Policy CI applicability classification fell back to full: {exc}",
                file=sys.stderr,
            )
            paths = []
            decision = Decision(
                True,
                "diff-unavailable",
                True,
                "diff-unavailable",
                "full",
            )

    print(
        "policy-ci-applicability "
        f"release_state={str(decision.release_state_required).lower()}"
        f"({decision.release_state_reason}) "
        f"trusted_review={str(decision.trusted_review_required).lower()}"
        f"({decision.trusted_review_reason}) "
        f"mode={decision.overall_reason} changed_count={len(paths)}"
    )
    for path in paths:
        print(f"changed: {path!r}")
    write_github_output(args.github_output, decision, count=len(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
