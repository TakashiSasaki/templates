#!/usr/bin/env python3
"""Classify whether a Site pull request needs expensive browser acceptance.

Delegates to the unified Site CI classifier (scripts/classify_site_ci.py).
Browser acceptance is required for browser-sensitive, PWA-sensitive,
runtime/build-sensitive, and CI control changes, or when forced.
Documentation-only and CI-observability changes safely skip browser acceptance.
Unknown or malformed input fails closed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.classify_site_ci import (
    ClassificationDecision,
    ClassificationError,
    classify_paths as classify_site_ci_paths,
    normalize_path,
)

SAFE_SKIP_EXACT_PATHS = frozenset(
    {
        ".github/workflows/ci-performance-report.yml",
        ".github/workflows/composition-unittest-timing-report.yml",
        "scripts/report_composition_unittest_timing.py",
    }
)
SAFE_SKIP_PREFIXES = ("tests/test_composition_unittest_timing_",)


def is_safe_skip_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized in SAFE_SKIP_EXACT_PATHS or normalized.startswith(
        SAFE_SKIP_PREFIXES
    )


def classify_paths(
    paths: Iterable[str],
    *,
    force_full: bool = False,
) -> tuple[bool, str, tuple[str, ...]]:
    decision = classify_site_ci_paths(paths, force_full=force_full)
    return decision.browser_required, decision.reason, decision.requiring_paths


def write_outputs(
    output: TextIO,
    *,
    required: bool,
    reason: str,
    changed_count: int,
    requiring_paths: tuple[str, ...],
) -> None:
    output.write(f"required={'true' if required else 'false'}\n")
    output.write(f"reason={reason}\n")
    output.write(f"changed_count={changed_count}\n")
    output.write(f"requiring_count={len(requiring_paths)}\n")
    if requiring_paths:
        output.write("requiring_paths=" + ",".join(requiring_paths) + "\n")
    else:
        output.write("requiring_paths=none\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force-full",
        type=lambda v: str(v).lower() in {"true", "1", "yes"},
        default=False,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = args.changed_paths.read_text(encoding="utf-8").splitlines()
        required, reason, requiring_paths = classify_paths(
            paths, force_full=args.force_full
        )
        with args.output.open("a", encoding="utf-8") as output:
            write_outputs(
                output,
                required=required,
                reason=reason,
                changed_count=len(paths),
                requiring_paths=requiring_paths,
            )
    except (OSError, UnicodeError, ClassificationError) as exc:
        print(f"Site browser acceptance classification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
