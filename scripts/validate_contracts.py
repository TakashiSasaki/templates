#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

MANIFEST_PATH = "contracts/manifest.json"
MANIFEST_SCHEMA_PATH = "schemas/contract-manifest.schema.json"
ROOT = Path(__file__).resolve().parents[1]

__all__ = (
    "SCHEMA_DIALECT",
    "VISUALLY_BLANK_CHARACTERS",
    "CONTRACT_SCHEMAS",
    "DuplicateKeyError",
    "NonStandardJsonConstantError",
    "load_json",
    "load_contract_manifest",
    "validate_contract_manifest",
    "registry_from_manifest",
    "load_contract_registry",
    "load_contract_documents",
    "cross_validate",
    "validate_repository",
    "main",
)

_IMPLEMENTATION: ModuleType | None = None


def _load_implementation() -> ModuleType:
    global _IMPLEMENTATION
    if _IMPLEMENTATION is None:
        _IMPLEMENTATION = importlib.import_module("validate_contracts_impl")
    return _IMPLEMENTATION


def __getattr__(name: str) -> Any:
    preflight_errors = _symlink_preflight(ROOT)
    if preflight_errors:
        if name == "CONTRACT_SCHEMAS":
            return {}
        details = "; ".join(preflight_errors)
        raise RuntimeError(
            f"cannot load validator attribute {name!r} before trust-boundary "
            f"preflight succeeds: {details}"
        )
    try:
        return getattr(_load_implementation(), name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def _path_contains_symlink(root: Path, relative: str) -> bool:
    path = Path(relative)
    if path.is_absolute():
        return False

    candidate = root
    for part in path.parts:
        if part in {"", "."}:
            continue
        candidate /= part
        if candidate.is_symlink():
            return True
    return False


def _directory_symlink_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for directory_name in ("contracts", "schemas"):
        directory = root / directory_name
        if directory.is_symlink():
            errors.append(
                f"{directory_name}: repository-owned directory must not be a symbolic link"
            )
            continue
        if not directory.is_dir():
            continue
        for current, directory_names, _ in os.walk(directory, followlinks=False):
            current_path = Path(current)
            for name in directory_names:
                candidate = current_path / name
                if candidate.is_symlink():
                    relative = candidate.relative_to(root).as_posix()
                    errors.append(
                        f"{relative}: repository-owned directory must not be a symbolic link"
                    )
    return errors


def _load_manifest_for_preflight(root: Path) -> dict[str, Any] | None:
    try:
        with (root / MANIFEST_PATH).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _symlink_preflight(root: Path) -> list[str]:
    if _path_contains_symlink(root, MANIFEST_PATH):
        return [f"{MANIFEST_PATH}: manifest must not be a symbolic link"]
    if _path_contains_symlink(root, MANIFEST_SCHEMA_PATH):
        return [
            f"{MANIFEST_SCHEMA_PATH}: bootstrap schema must not be a symbolic link"
        ]

    directory_errors = _directory_symlink_errors(root)
    if directory_errors:
        return directory_errors

    manifest = _load_manifest_for_preflight(root)
    if manifest is None:
        return []

    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        return []

    errors: list[str] = []
    registered_schemas: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        contract_id = entry.get("id")
        schema_path = entry.get("schema")
        if isinstance(schema_path, str):
            registered_schemas.add(schema_path)
        for label in ("document", "schema"):
            relative = entry.get(label)
            if (
                isinstance(contract_id, str)
                and isinstance(relative, str)
                and _path_contains_symlink(root, relative)
            ):
                errors.append(
                    f"contract manifest {contract_id}: {label} must not be a symbolic link: "
                    f"{relative}"
                )

    actual_schemas = {
        path.relative_to(root).as_posix()
        for path in (root / "schemas").rglob("*.json")
        if path.is_file() or path.is_symlink()
    } - {MANIFEST_SCHEMA_PATH}
    for relative in sorted(actual_schemas - registered_schemas):
        errors.append(f"unregistered contract schema: {relative}")

    return errors


def _document_metadata_errors(root: Path, implementation: ModuleType) -> list[str]:
    manifest = implementation.load_contract_manifest(root)
    errors: list[str] = []
    for entry in manifest["contracts"]:
        document_path = entry["document"]
        document = implementation.load_json(root / document_path)
        if not isinstance(document, dict):
            errors.append(
                f"{document_path}: registered contract document must be a JSON object "
                "with $schema and schemaVersion metadata"
            )
    return errors


def validate_repository(root: Path) -> list[str]:
    errors = _symlink_preflight(root)
    if errors:
        return errors
    implementation = _load_implementation()
    errors = implementation.validate_repository(root)
    if errors:
        return errors
    return _document_metadata_errors(root, implementation)


def main() -> int:
    errors = validate_repository(ROOT)
    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All web-application contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
