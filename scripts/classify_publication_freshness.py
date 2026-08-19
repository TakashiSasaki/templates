#!/usr/bin/env python3
"""Classify a reviewed Composition lock against an exact current snapshot."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


FULL_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class PublicationFreshnessError(RuntimeError):
    """Raised when publication freshness inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locked", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def validate_revision(label: str, value: str) -> str:
    if not FULL_COMMIT_PATTERN.fullmatch(value):
        raise PublicationFreshnessError(
            f"{label} Composition revision must be a full lowercase commit SHA"
        )
    return value


def classify(locked: str, current: str) -> str:
    locked_revision = validate_revision("locked", locked)
    current_revision = validate_revision("current", current)
    return "current" if locked_revision == current_revision else "different"


def write_relation(output: Path | None, relation: str) -> None:
    if output is None:
        print(relation)
        return
    with output.open("a", encoding="utf-8") as stream:
        stream.write(f"relation={relation}\n")


def main() -> int:
    args = parse_args()
    try:
        write_relation(args.output, classify(args.locked, args.current))
    except (OSError, PublicationFreshnessError) as exc:
        print(f"publication freshness classification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
