#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

EXPECTED_SKILL_NAME = "composition"


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
            if (
                len(parsed) >= 2
                and parsed[0] == parsed[-1]
                and parsed[0] in {'"', "'"}
            ):
                parsed = parsed[1:-1]
            if name is not None and parsed != name:
                return None
            name = parsed
    return None


def is_composition_skill_directory(target: Path) -> bool:
    marker = target / "SKILL.md"
    return (
        not marker.is_symlink()
        and marker.is_file()
        and read_front_matter_name(marker) == EXPECTED_SKILL_NAME
    )


def stage_and_install(source: Path, target: Path, *, replace: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.install-", dir=target.parent)
    )
    staged = temporary_root / "staged"
    backup = temporary_root / "backup"
    preserve_temporary_root = False
    try:
        shutil.copytree(
            source,
            staged,
            ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"),
        )
        if not replace:
            staged.rename(target)
            return

        target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            try:
                backup.rename(target)
            except OSError as restore_error:
                preserve_temporary_root = True
                raise RuntimeError(
                    "replacement failed and the previous installation could not be "
                    f"restored; backup preserved at {backup}"
                ) from restore_error
            raise
        shutil.rmtree(backup)
    finally:
        if not preserve_temporary_root:
            shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Composition skill")
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

    replace = target.exists()
    if replace:
        if not args.replace:
            parser.error(f"target already exists: {target}")
        if not is_composition_skill_directory(target):
            parser.error("refusing to replace a directory that is not this skill")
    stage_and_install(source, target, replace=replace)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
