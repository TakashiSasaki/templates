#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "release/skill-installer.json"
SCHEMA = ROOT / "schemas/skill-installer-release.schema.json"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_REVISION = re.compile(
    r'^SKILL_SOURCE_REVISION = "([0-9a-f]{40})"$', re.MULTILINE
)
REPOSITORY_IDENTITY = 'TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"'
REQUIRED_SKILL_PATHS = (
    "SKILL.md",
    "runtime-manifest.json",
    "scripts/install.py",
)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path.relative_to(ROOT)}")
    return value


def git_text(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    )


def validate_schema(value: object, schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "root"
    raise ValueError(
        f"Invalid skill installer release at {location}: {errors[0].message}"
    )


def require_file(revision: str, path: str) -> str:
    try:
        return git_text("show", f"{revision}:{path}")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Pinned revision {revision} is missing required path: {path}"
        ) from exc


def require_ancestor(revision: str, git_ref: str, label: str) -> None:
    source_commit = git_text("rev-parse", f"{git_ref}^{{commit}}").strip()
    if source_commit == revision:
        raise ValueError(f"{label} revision must precede its publication commit")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, source_commit],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"{label} revision {revision} is not an ancestor of {git_ref}")


def verify(git_ref: str | None = None) -> tuple[str, str]:
    descriptor = load_object(DESCRIPTOR)
    validate_schema(descriptor, load_object(SCHEMA))

    installer = descriptor["installer"]
    skill_source = descriptor["skill_source"]
    if not isinstance(installer, dict) or not isinstance(skill_source, dict):
        raise ValueError("Installer release entries must be objects")

    installer_revision = installer["revision"]
    skill_revision = skill_source["revision"]
    if not isinstance(installer_revision, str) or FULL_SHA.fullmatch(installer_revision) is None:
        raise ValueError("Installer revision must be a full lowercase commit SHA")
    if not isinstance(skill_revision, str) or FULL_SHA.fullmatch(skill_revision) is None:
        raise ValueError("Skill source revision must be a full lowercase commit SHA")

    installer_path = str(installer["path"])
    installer_source = require_file(installer_revision, installer_path)
    if REPOSITORY_IDENTITY not in installer_source:
        raise ValueError("Pinned installer does not identify TakashiSasaki/templates")
    match = SOURCE_REVISION.search(installer_source)
    if match is None:
        raise ValueError("Pinned installer does not declare one full skill source revision")
    if match.group(1) != skill_revision:
        raise ValueError(
            "Pinned installer skill source revision differs from publication descriptor"
        )

    skill_root = str(skill_source["path"]).rstrip("/")
    for relative in REQUIRED_SKILL_PATHS:
        require_file(skill_revision, f"{skill_root}/{relative}")

    if git_ref:
        require_ancestor(installer_revision, git_ref, "Installer")
        require_ancestor(skill_revision, git_ref, "Skill source")

    return installer_revision, skill_revision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the immutable agent-policy skill installer publication."
    )
    parser.add_argument(
        "--git-ref",
        help="Require both pinned revisions to be strict ancestors of this Git ref.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        installer_revision, skill_revision = verify(args.git_ref)
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"skill installer release verification error: {exc}", file=sys.stderr)
        return 1
    print(
        "Skill installer release is synchronized: "
        f"installer={installer_revision}, skill={skill_revision}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
