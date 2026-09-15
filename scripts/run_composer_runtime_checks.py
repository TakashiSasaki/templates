#!/usr/bin/env python3
"""Run the canonical Composition consumer-runtime checks used locally and in CI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS: dict[str, tuple[str, ...]] = {
    "clean-runtime": ("smoke_test_runtime_distribution.py",),
    "materialized-validation": ("smoke_test_materialized_validation.py",),
    "skill-runner": (
        "smoke_test_skill_runner.py",
        "smoke_test_remote_skill_installer.py",
    ),
}
GROUPS: dict[str, tuple[str, ...]] = {
    "runtime-core": ("clean-runtime", "materialized-validation"),
    "all": ("runtime-core", "skill-runner"),
}


def selected_scripts(check: str) -> tuple[str, ...]:
    groups = GROUPS.get(check)
    if groups is None:
        return CHECKS[check]
    return tuple(script for group in groups for script in selected_scripts(group))


def run_checks(check: str) -> None:
    for script in selected_scripts(check):
        subprocess.run(
            [sys.executable, "-I", str(ROOT / "scripts" / script)],
            cwd=ROOT,
            check=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the same Composition consumer-runtime smoke checks used by "
            "the default and explicit compatibility workflows."
        )
    )
    parser.add_argument(
        "--check",
        choices=(*GROUPS, *CHECKS),
        default="all",
        help="Run every runtime surface, one CI group, or one focused surface.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_checks(args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
