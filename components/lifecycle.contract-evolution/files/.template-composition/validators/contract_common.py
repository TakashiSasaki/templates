#!/usr/bin/env python3
"""Shared helpers for composition lifecycle validators."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class DuplicateKeyError(ValueError):
    pass


class NonStandardJsonConstantError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> Any:
    raise NonStandardJsonConstantError(f"non-standard JSON numeric constant {value!r}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "contracts/manifest.json"
    if path.is_symlink():
        raise ValueError("contracts/manifest.json must not be a symbolic link")
    value = load_json(path)
    if not isinstance(value, dict):
        raise TypeError("contracts/manifest.json must contain an object")
    return value


def contract_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("contracts", [])
    return {entry["id"]: entry for entry in entries}


def parse_timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("timestamp must end in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
