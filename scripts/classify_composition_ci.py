#!/usr/bin/env python3
"""Classify whether Composition behavioral CI is required."""

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
SAFE_DOCUMENTATION_PREFIXES = ("docs/", "translations/")
SAFE_DOCUMENTATION_FILES = frozenset({"README.md"})
REAL_BROWSER_REQUIRED_PREFIXES = (
    "catalog/",
    "components/",
    "generated/",
    "recipes/",
    "release/",
    "schemas/",
    "skills/composition/scripts/",
)
REAL_BROWSER_REQUIRED_FILES = frozenset(
    {
        ".github/workflows/schema-validation.yml",
        "requirements-dev.lock",
        "requirements-runtime.lock",
        "scripts/compose.py",
        "scripts/composer_apply.py",
        "scripts/composer_cli_messages.py",
        "scripts/composer_core.py",
        "scripts/composer_core_impl.py",
        "scripts/composer_human_output.py",
        "scripts/composer_managed.py",
        "scripts/composer_managed_impl.py",
        "scripts/composer_post_apply.py",
        "scripts/composer_source.py",
        "scripts/composer_transaction.py",
        "scripts/composer_update_plan.py",
        "scripts/composer_upgrade.py",
        "scripts/composition_phase_zero.py",
        "scripts/generate_composition_playground.py",
        "scripts/generate_composition_playground_intent.py",
        "scripts/generate_composition_playground_publication.py",
        "scripts/materialize_publication.py",
        "scripts/run_unittest_shard.py",
        "scripts/validate_component_versions.py",
        "scripts/validate_playground_provenance.py",
        "scripts/validate_publication.py",
    }
)
REAL_BROWSER_TEST_NAME_PARTS = (
    "browser",
    "pwa",
    "task_ledger",
    "webapp",
    "website",
)
REAL_BROWSER_TEST_FILES = frozenset(
    {"tests/test_selected_component_validation.py"}
)
REAL_BROWSER_INSENSITIVE_SCRIPT_FILES = frozenset(
    {
        "scripts/check_python_dependencies.py",
        "scripts/classify_composition_ci.py",
        "scripts/run_composition_consumer_smoke.py",
        "scripts/run_composition_preflight.py",
        "scripts/smoke_test_materialized_validation.py",
        "scripts/smoke_test_remote_skill_installer.py",
        "scripts/smoke_test_runtime_distribution.py",
        "scripts/smoke_test_skill_runner.py",
        "scripts/validate_translations.py",
        "scripts/verify_composition_skill_installer_release.py",
        "scripts/verify_runtime_environment.py",
    }
)


class ClassificationError(RuntimeError):
    """Raised when a Git diff cannot be classified safely."""


def is_safe_repository_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    return all(part not in {"", ".", ".."} for part in path.split("/"))


def is_documentation_only_path(path: str) -> bool:
    """Return whether one trusted repository path is safe to skip in behavioral CI."""
    if not is_safe_repository_path(path):
        return False
    if path in SAFE_DOCUMENTATION_FILES:
        return True
    return any(path.startswith(prefix) for prefix in SAFE_DOCUMENTATION_PREFIXES)


def classify_paths(paths: Sequence[str]) -> tuple[bool, str]:
    """Return (behavioral_ci_required, stable_reason) for one changed-path set."""
    if not paths:
        return True, "no-changes"
    for path in paths:
        if not is_documentation_only_path(path):
            return True, "composition-sensitive-change"
    return False, "documentation-only"


def is_real_browser_test_path(path: str) -> bool:
    """Return whether a test or fixture belongs to Webapp/browser behavior."""
    if path in REAL_BROWSER_TEST_FILES:
        return True
    if path.startswith(("tests/fixtures/webapp_", "tests/fixtures/browser/")):
        return True
    if not path.startswith("tests/test_"):
        return False
    name = Path(path).name.lower()
    return any(part in name for part in REAL_BROWSER_TEST_NAME_PARTS)


def is_real_browser_required_path(path: str) -> bool:
    """Return whether a path can change the generated Webapp or browser proof."""
    if not is_safe_repository_path(path):
        return True
    if path.startswith("release/") and path.endswith((".md", ".txt")):
        return False
    if path in REAL_BROWSER_REQUIRED_FILES:
        return True
    if any(path.startswith(prefix) for prefix in REAL_BROWSER_REQUIRED_PREFIXES):
        return True
    if path.startswith("skills/composition/") and not path.endswith(".md"):
        return True
    return is_real_browser_test_path(path)


def is_known_real_browser_insensitive_path(path: str) -> bool:
    """Return whether a trusted path is outside the Webapp/browser proof."""
    if not is_safe_repository_path(path):
        return False
    if is_documentation_only_path(path):
        return True
    if path in {"AGENTS.md", ".agent-policy.yml", "examples/README.md"}:
        return True
    if path.startswith((".agents/", ".github/", "tests/")):
        return True
    if path.startswith("skills/composition/") and path.endswith(".md"):
        return True
    if path.startswith("release/") and path.endswith((".md", ".txt")):
        return True
    return path in REAL_BROWSER_INSENSITIVE_SCRIPT_FILES


def classify_real_browser_paths(paths: Sequence[str]) -> tuple[bool, str]:
    """Classify Chrome acceptance independently of the general runtime checks."""
    if not paths:
        return True, "no-changes"
    for path in paths:
        if not is_safe_repository_path(path):
            return True, "ambiguous-path"
        if is_real_browser_required_path(path):
            return True, "webapp-or-browser-change"
        if not is_known_real_browser_insensitive_path(path):
            return True, "unclassified-change"
    return False, "browser-insensitive-change"


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


def write_github_output(
    path: Path,
    *,
    required: bool,
    reason: str,
    count: int,
) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"required={'true' if required else 'false'}\n")
        output.write(f"reason={reason}\n")
        output.write(f"changed_count={count}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("behavioral", "real-browser"),
        default="behavioral",
        help="select the unchanged behavioral gate or the narrower Chrome gate",
    )
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.base == ZERO_SHA:
        required, reason, paths = True, "unbounded-push", []
    else:
        try:
            paths = changed_paths(args.base, args.head)
            classifier = (
                classify_real_browser_paths
                if args.profile == "real-browser"
                else classify_paths
            )
            required, reason = classifier(paths)
        except ClassificationError as exc:
            print(
                f"Composition CI classification fell back to required: {exc}",
                file=sys.stderr,
            )
            required, reason, paths = True, "diff-unavailable", []

    print(
        f"composition-ci profile={args.profile} "
        f"required={str(required).lower()} reason={reason} "
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
