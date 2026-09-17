#!/usr/bin/env python3
"""Collect pull-request paths without collapsing base failures into empty input."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


SITE_MARKERS = (
    ".github/workflows/build-pages.yml",
    "scripts/classify_site_ci.py",
)

# The workflow uses these statuses to keep a valid non-Site or empty diff
# distinct from a failure that must escalate to full Site qualification.
NON_SITE = 10
BASE_UNAVAILABLE = 20
DIFF_UNAVAILABLE = 21


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def collect(root: Path, base_sha: str, head_sha: str, output: Path) -> int:
    base_tree = _git(root, "ls-tree", "-r", "--name-only", base_sha)
    if base_tree.returncode != 0:
        return BASE_UNAVAILABLE
    if not all(marker in base_tree.stdout.splitlines() for marker in SITE_MARKERS):
        return NON_SITE

    changed = _git(root, "diff", "--name-only", "--no-renames", base_sha, head_sha)
    if changed.returncode != 0:
        return DIFF_UNAVAILABLE
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(changed.stdout, encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return collect(args.root, args.base, args.head, args.output)


if __name__ == "__main__":
    sys.exit(main())
