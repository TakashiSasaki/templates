#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXPECTED_SKILL_NAME = "bootstrap-agent-policy"


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def read_front_matter_name(marker: Path) -> str | None:
    try:
        lines = marker.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None

    name: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            return name
        if not line or line.startswith((" ", "\t", "#")):
            continue
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            parsed = value.strip()
            if len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in {'"', "'"}:
                parsed = parsed[1:-1]
            if name is not None and parsed != name:
                return None
            name = parsed
    return None


def is_bootstrap_skill_directory(target: Path) -> bool:
    marker = target / "SKILL.md"
    return marker.is_file() and read_front_matter_name(marker) == EXPECTED_SKILL_NAME


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the bootstrap-agent-policy skill")
    parser.add_argument("target", type=Path, help="Destination skill directory")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    source = skill_root().resolve()
    target = args.target.expanduser().absolute()
    if target.is_symlink():
        parser.error("target skill directory must not be a symbolic link")
    resolved_target = target.resolve(strict=False)
    if paths_overlap(source, resolved_target):
        parser.error("source and target skill directories must not overlap")
    if target.exists():
        if not args.replace:
            parser.error(f"target already exists: {target}")
        if not is_bootstrap_skill_directory(target):
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
