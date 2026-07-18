from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from .yamlutil import dump_yaml, load_yaml


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


def load_lock_output_paths(path: Path) -> tuple[str, ...]:
    value = load_yaml(path)
    if not isinstance(value, dict):
        raise ValueError("Lock file root must be a mapping")
    if value.get("lock_version") != 1:
        raise ValueError("Unsupported lock file version")

    outputs = value.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Lock file outputs must be a mapping")

    result: list[str] = []
    for relative, metadata in outputs.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError("Lock output paths must be non-empty strings")
        if not isinstance(metadata, dict):
            raise ValueError(f"Lock output metadata must be a mapping: {relative}")
        digest = metadata.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"Lock output sha256 is invalid: {relative}")
        result.append(relative)
    return tuple(sorted(result))
