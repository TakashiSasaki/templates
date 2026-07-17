from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from .yamlutil import dump_yaml


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_lock(
    *,
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
        "inputs": {name: {"sha256": file_hash(path)} for name, path in sorted(inputs.items())},
        "outputs": {name: {"sha256": file_hash(path)} for name, path in sorted(outputs.items())},
    }
    return dump_yaml(value)
