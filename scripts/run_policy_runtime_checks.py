#!/usr/bin/env python3
"""Run the canonical Policy runtime checks used locally and in CI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALID_CHECKS = ("all", "runtime", "skill-source")


def commands_for(
    check: str,
    revision: str | None,
) -> tuple[tuple[str, ...], ...]:
    commands: list[tuple[str, ...]] = []
    if check in {"all", "runtime"}:
        commands.append(
            (
                sys.executable,
                "-I",
                str(ROOT / "scripts/run_policy_preflight.py"),
                "--check",
                "runtime",
            )
        )
    if check in {"all", "skill-source"}:
        if not revision:
            raise ValueError("--revision is required for the skill-source check")
        commands.append(
            (
                sys.executable,
                "-I",
                str(ROOT / "scripts/smoke_test_agent_policy_skill_source.py"),
                "--revision",
                revision,
            )
        )
    return tuple(commands)


def run_checks(check: str, revision: str | None) -> None:
    for command in commands_for(check, revision):
        subprocess.run(command, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the same Policy runtime checks used by the default and explicit "
            "compatibility workflow tiers."
        )
    )
    parser.add_argument(
        "--check",
        choices=VALID_CHECKS,
        default="all",
        help="Run the clean runtime check, the skill-source check, or both.",
    )
    parser.add_argument(
        "--revision",
        help="Exact candidate commit SHA required by the skill-source check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_checks(args.check, args.revision)
    except ValueError as exc:
        print(f"policy runtime check configuration error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
