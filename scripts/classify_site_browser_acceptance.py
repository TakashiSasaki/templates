#!/usr/bin/env python3
"""Classify whether a Site pull request needs expensive browser acceptance.

The first optimization boundary is deliberately narrow. Browser acceptance may be
skipped only when every changed path is an explicitly listed CI-observability
surface that cannot alter the generated reader-facing Site or browser runtime.
Everything else, including this classifier and the build workflow that invokes it,
requires browser acceptance. Unknown or malformed input fails closed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, TextIO


SAFE_SKIP_EXACT_PATHS = frozenset(
    {
        ".github/workflows/ci-performance-report.yml",
        ".github/workflows/composition-unittest-timing-report.yml",
        "scripts/report_composition_unittest_timing.py",
    }
)
SAFE_SKIP_PREFIXES = ("tests/test_composition_unittest_timing_",)


class ClassificationError(ValueError):
    """Raised when changed-path input cannot be classified safely."""


def normalize_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    if not path:
        raise ClassificationError("changed path must not be empty")
    parts = path.split("/")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ClassificationError(
            f"changed path is not repository-relative: {value!r}"
        )
    return path


def is_safe_skip_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized in SAFE_SKIP_EXACT_PATHS or normalized.startswith(
        SAFE_SKIP_PREFIXES
    )


def classify_paths(paths: Iterable[str]) -> tuple[bool, str, tuple[str, ...]]:
    normalized = tuple(normalize_path(path) for path in paths)
    if not normalized:
        raise ClassificationError("at least one changed path is required")

    requiring = tuple(
        sorted({path for path in normalized if not is_safe_skip_path(path)})
    )
    if requiring:
        return True, "non-observability path changed", requiring
    return False, "all changed paths are CI-observability-only", tuple()


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = args.changed_paths.read_text(encoding="utf-8").splitlines()
        required, reason, requiring_paths = classify_paths(paths)
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
