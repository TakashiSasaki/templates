#!/usr/bin/env python3
"""Verify that tracked repository tooling no longer depends on Ruby."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("Unable to enumerate tracked files.", file=sys.stderr)
        return 1

    failures: list[str] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = PurePosixPath(relative)
        if path.suffix.lower() in {".rb", ".rake", ".gemspec"}:
            failures.append(relative)
        if path.name in {"Gemfile", "Gemfile.lock", "Rakefile", ".ruby-version"}:
            failures.append(relative)
        if ".bundle" in path.parts:
            failures.append(relative)

    if failures:
        for relative in sorted(set(failures)):
            print(f"Ruby tooling remains: {relative}", file=sys.stderr)
        return 1

    print("No active Ruby tooling remains.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
