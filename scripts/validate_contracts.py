#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import validate_contracts_impl as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


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


def _symlink_preflight(root: Path) -> list[str]:
    if _path_contains_symlink(root, _impl.MANIFEST_PATH):
        return [
            f"{_impl.MANIFEST_PATH}: manifest must not be a symbolic link"
        ]
    if _path_contains_symlink(root, _impl.MANIFEST_SCHEMA_PATH):
        return [
            f"{_impl.MANIFEST_SCHEMA_PATH}: bootstrap schema must not be a symbolic link"
        ]

    directory_errors = _directory_symlink_errors(root)
    if directory_errors:
        return directory_errors

    try:
        manifest = _impl.load_contract_manifest(root)
    except _impl._load_json_error_types():
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
                    f"contract manifest {contract_id}: {label} must not be "
                    f"a symbolic link: {relative}"
                )

    actual_schemas = {
        path.relative_to(root).as_posix()
        for path in (root / "schemas").rglob("*.json")
        if path.is_file() or path.is_symlink()
    } - {_impl.MANIFEST_SCHEMA_PATH}
    for relative in sorted(actual_schemas - registered_schemas):
        errors.append(f"unregistered contract schema: {relative}")

    return errors


def _document_metadata_errors(root: Path) -> list[str]:
    manifest = _impl.load_contract_manifest(root)
    errors: list[str] = []
    for entry in manifest["contracts"]:
        document_path = entry["document"]
        document = _impl.load_json(root / document_path)
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
    errors = _impl.validate_repository(root)
    if errors:
        return errors
    return _document_metadata_errors(root)


def main() -> int:
    errors = validate_repository(_impl.ROOT)
    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All web-application contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
