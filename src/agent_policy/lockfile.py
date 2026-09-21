from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .paths import UnsafePathError, resolve_inside
from .yamlutil import dump_yaml, load_yaml

LOCK_PATH = ".agent-policy.lock"


def resolve_lock_path(repository_root: Path, *, allow_missing: bool = True) -> Path:
    literal = repository_root.resolve() / LOCK_PATH
    if literal.is_symlink():
        raise UnsafePathError(f"Lock path must not be a symlink: {LOCK_PATH}")
    return resolve_inside(repository_root, LOCK_PATH, allow_missing=allow_missing)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def create_lock(
    toolchain_repository: str,
    toolchain_revision: str,
    inputs: Mapping[str, Path],
    outputs: Mapping[str, Path],
) -> str:
    value = {
        "lock_version": 1,
        "toolchain": {
            "repository": toolchain_repository,
            "revision": toolchain_revision,
        },
        "inputs": {name: {"sha256": sha256_file(path)} for name, path in sorted(inputs.items())},
        "outputs": {name: {"sha256": sha256_file(path)} for name, path in sorted(outputs.items())},
    }
    return dump_yaml(value)


def _load_lock_section(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"Lock file {label} must be a mapping")

    result: dict[str, str] = {}
    for relative, metadata in value.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"Lock {label} paths must be non-empty strings")
        if not isinstance(metadata, dict):
            raise ValueError(f"Lock {label} metadata must be a mapping: {relative}")
        digest = metadata.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"Lock {label} sha256 is invalid: {relative}")
        result[relative] = digest
    return dict(sorted(result.items()))


def load_lock(path: Path) -> dict[str, Any]:
    value = load_yaml(path)
    if not isinstance(value, dict):
        raise ValueError("Lock file root must be a mapping")
    if value.get("lock_version") != 1:
        raise ValueError("Unsupported lock file version")

    toolchain = value.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError("Lock file toolchain must be a mapping")
    repository = toolchain.get("repository")
    revision = toolchain.get("revision")
    if not isinstance(repository, str) or not repository:
        raise ValueError("Lock file toolchain repository is invalid")
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise ValueError("Lock file toolchain revision is invalid")

    return {
        "lock_version": 1,
        "toolchain": {"repository": repository, "revision": revision},
        "inputs": _load_lock_section(value.get("inputs"), "input"),
        "outputs": _load_lock_section(value.get("outputs"), "output"),
    }


def load_lock_outputs(path: Path) -> dict[str, str]:
    return load_lock(path)["outputs"]


def load_lock_inputs(path: Path) -> dict[str, str]:
    return load_lock(path)["inputs"]


def load_lock_output_paths(path: Path) -> tuple[str, ...]:
    return tuple(load_lock_outputs(path))
