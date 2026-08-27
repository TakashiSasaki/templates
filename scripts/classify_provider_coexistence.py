#!/usr/bin/env python3
"""Classify whether a Site PR requires provider coexistence integration.

The coexistence harness executes Site-owned Python integration tooling against the
exact provider revisions in ``publication-sources.json``.  To stay fail-closed,
all Site Python tooling changes are treated as relevant; non-Python Site content
can skip the heavy provider setup unless it changes the workflow or provider lock
itself.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, TextIO

REQUIRED_EXACT_PATHS = frozenset(
    {
        ".github/workflows/provider-coexistence.yml",
        "publication-sources.json",
    }
)
REQUIRED_SUFFIXES = (".py",)


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


def requires_provider_coexistence(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized in REQUIRED_EXACT_PATHS or normalized.endswith(REQUIRED_SUFFIXES)


def classify_paths(paths: Iterable[str]) -> tuple[bool, tuple[str, ...]]:
    normalized = tuple(normalize_path(path) for path in paths)
    if not normalized:
        raise ClassificationError("at least one changed path is required")
    matched = tuple(
        sorted(
            {
                path
                for path in normalized
                if requires_provider_coexistence(path)
            }
        )
    )
    return bool(matched), matched


def write_outputs(output: TextIO, *, required: bool, matched: tuple[str, ...]) -> None:
    output.write(f"required={'true' if required else 'false'}\n")
    output.write(f"matched_count={len(matched)}\n")
    if matched:
        output.write("matched_paths=" + ",".join(matched) + "\n")
    else:
        output.write("matched_paths=none\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = args.changed_paths.read_text(encoding="utf-8").splitlines()
        required, matched = classify_paths(paths)
        with args.output.open("a", encoding="utf-8") as output:
            write_outputs(output, required=required, matched=matched)
    except (OSError, UnicodeError, ClassificationError) as exc:
        raise SystemExit(f"provider coexistence classification failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
