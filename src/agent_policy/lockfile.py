from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from .yamlutil import dump_yaml


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
