#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the bootstrap-agent-policy skill")
    parser.add_argument("target", type=Path, help="Destination skill directory")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.target.expanduser().resolve()
    if target.exists():
        if not args.replace:
            parser.error(f"target already exists: {target}")
        marker = target / "SKILL.md"
        if not marker.is_file() or "name: bootstrap-agent-policy" not in marker.read_text(
            encoding="utf-8"
        ):
            parser.error("refusing to replace a directory that is not this skill")
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"),
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
