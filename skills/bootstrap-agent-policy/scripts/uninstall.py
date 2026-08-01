#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Uninstall the bootstrap-agent-policy skill")
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    marker = target / "SKILL.md"
    if not marker.is_file() or "name: bootstrap-agent-policy" not in marker.read_text(
        encoding="utf-8"
    ):
        parser.error("target is not a bootstrap-agent-policy skill directory")
    shutil.rmtree(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
