#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "release" / "composition-installer.json"
SCHEMA = ROOT / "schemas" / "composition-skill-installer-release.schema.json"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_REVISION = re.compile(
    r'^SKILL_SOURCE_REVISION = "([0-9a-f]{40})"$', re.MULTILINE
)
REPOSITORY_IDENTITY = 'TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"'
CANONICAL_REPOSITORY = "TakashiSasaki/templates"
REQUIRED_SKILL_PATHS = (
    "SKILL.md",
    "runtime-manifest.json",
    "scripts/install.py",
    "scripts/run.py",
    "scripts/run_checkout.py",
    "scripts/runtime.py",
    "scripts/runtime_checkout.py",
)
REQUIRED_TOOLCHAIN_PATHS = (
    "requirements-runtime.lock",
    "scripts/compose.py",
    "scripts/composer_core.py",
    "scripts/composer_core_impl.py",
    "scripts/composer_managed.py",
    "scripts/composer_managed_impl.py",
    "scripts/composer_source.py",
    "scripts/verify_runtime_environment.py",
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def parse_object(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text, object_pairs_hook=_unique_object)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot parse {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def load_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    return parse_object(text, str(path.relative_to(ROOT)))


def git_bytes(*arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, stderr=subprocess.STDOUT
    )


def git_text(*arguments: str) -> str:
    try:
        return git_bytes(*arguments).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"git output is not UTF-8 for: {' '.join(arguments)}") from exc


def require_file(revision: str, path: str) -> bytes:
    try:
        return git_bytes("show", f"{revision}:{path}")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"pinned revision {revision} is missing required path: {path}"
        ) from exc


def require_text_file(revision: str, path: str) -> str:
    data = require_file(revision, path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"pinned file is not UTF-8: {revision}:{path}") from exc


def validate_schema(value: object, schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "root"
    raise ValueError(
        f"invalid Composition installer release at {location}: {errors[0].message}"
    )


def full_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} revision must be a full lowercase commit SHA")
    return value


def require_strict_ancestor(ancestor: str, descendant: str, label: str) -> None:
    if ancestor == descendant:
        raise ValueError(f"{label} must be a strict ancestor")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise ValueError(
            f"{label} ancestry is invalid: {ancestor} is not an ancestor of {descendant}"
        )


def verify(git_ref: str | None = None) -> tuple[str, str, str]:
    descriptor = load_object(DESCRIPTOR)
    validate_schema(descriptor, load_object(SCHEMA))

    installer = descriptor["installer"]
    skill_source = descriptor["skill_source"]
    toolchain = descriptor["toolchain"]
    if not isinstance(installer, dict):
        raise ValueError("installer release entry must be an object")
    if not isinstance(skill_source, dict):
        raise ValueError("skill_source release entry must be an object")
    if not isinstance(toolchain, dict):
        raise ValueError("toolchain release entry must be an object")

    installer_revision = full_sha(installer.get("revision"), "installer")
    skill_revision = full_sha(skill_source.get("revision"), "skill source")
    toolchain_revision = full_sha(toolchain.get("revision"), "toolchain")

    installer_path = str(installer["path"])
    installer_source = require_text_file(installer_revision, installer_path)
    if REPOSITORY_IDENTITY not in installer_source:
        raise ValueError("pinned installer does not identify TakashiSasaki/templates")
    source_match = SOURCE_REVISION.search(installer_source)
    if source_match is None:
        raise ValueError("pinned installer does not declare one full skill source revision")
    if source_match.group(1) != skill_revision:
        raise ValueError(
            "pinned installer skill source revision differs from release descriptor"
        )

    skill_root = str(skill_source["path"]).rstrip("/")
    for relative in REQUIRED_SKILL_PATHS:
        require_file(skill_revision, f"{skill_root}/{relative}")

    runtime_manifest = parse_object(
        require_text_file(skill_revision, f"{skill_root}/runtime-manifest.json"),
        "pinned skill runtime manifest",
    )
    schema_version = runtime_manifest.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("pinned skill runtime manifest schema is unsupported")
    if runtime_manifest.get("toolchain") != {
        "repository": CANONICAL_REPOSITORY,
        "revision": toolchain_revision,
    }:
        raise ValueError(
            "pinned skill runtime manifest toolchain differs from release descriptor"
        )
    runtime_lock = runtime_manifest.get("runtime_lock")
    if not isinstance(runtime_lock, dict) or set(runtime_lock) != {"path", "sha256"}:
        raise ValueError("pinned skill runtime lock declaration is invalid")
    if runtime_lock.get("path") != "requirements-runtime.lock":
        raise ValueError("pinned skill runtime lock path is unsupported")
    expected_lock_digest = runtime_lock.get("sha256")
    if not isinstance(expected_lock_digest, str) or re.fullmatch(
        r"[0-9a-f]{64}", expected_lock_digest
    ) is None:
        raise ValueError("pinned skill runtime lock digest is invalid")
    if runtime_manifest.get("entrypoint") != "scripts/compose.py":
        raise ValueError("pinned skill Composer entrypoint is unsupported")

    for path in REQUIRED_TOOLCHAIN_PATHS:
        require_file(toolchain_revision, path)
    lock_data = require_file(toolchain_revision, "requirements-runtime.lock")
    actual_lock_digest = hashlib.sha256(lock_data).hexdigest()
    if actual_lock_digest != expected_lock_digest:
        raise ValueError(
            "pinned toolchain runtime lock digest differs from skill runtime manifest"
        )

    require_strict_ancestor(
        toolchain_revision, skill_revision, "stable toolchain -> skill source"
    )
    require_strict_ancestor(
        skill_revision, installer_revision, "skill source -> installer"
    )

    if git_ref is not None:
        publication_revision = full_sha(
            git_text("rev-parse", "--verify", f"{git_ref}^{{commit}}", "--").strip(),
            "publication",
        )
        require_strict_ancestor(
            installer_revision, publication_revision, "installer -> publication"
        )
        require_strict_ancestor(
            skill_revision, publication_revision, "skill source -> publication"
        )
        require_strict_ancestor(
            toolchain_revision, publication_revision, "stable toolchain -> publication"
        )

    return installer_revision, skill_revision, toolchain_revision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify immutable Composition installer publication identities."
    )
    parser.add_argument(
        "--git-ref",
        help="Require every published revision to be a strict ancestor of this Git ref.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        installer_revision, skill_revision, toolchain_revision = verify(args.git_ref)
    except (KeyError, OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Composition installer release verification error: {exc}", file=sys.stderr)
        return 1
    print(
        "Composition installer release is synchronized: "
        f"installer={installer_revision}, skill={skill_revision}, "
        f"toolchain={toolchain_revision}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
