#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import importlib
import json
import os
import stat
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
        module_name = (
            f"{__package__}.validate_contracts_impl"
            if __package__
            else "validate_contracts_impl"
        )
        _IMPLEMENTATION = importlib.import_module(module_name)
    return _IMPLEMENTATION


def _loader_preflight(name: str, root: Path) -> None:
    """Reject unsafe facade or caller roots before loading implementation code."""

    errors = _symlink_preflight(ROOT, check_inventory=False)
    if not errors:
        errors = _symlink_preflight(root, check_inventory=False)
    if errors:
        details = "; ".join(errors)
        raise RuntimeError(
            f"cannot call validator loader {name!r} before trust-boundary "
            f"preflight succeeds: {details}"
        )


def _load_contract_manifest(root: Path) -> dict[str, Any]:
    _loader_preflight("load_contract_manifest", root)
    return _load_implementation().load_contract_manifest(root)


def _load_contract_registry(root: Path) -> dict[str, tuple[str, str]]:
    _loader_preflight("load_contract_registry", root)
    return _load_implementation().load_contract_registry(root)


def _load_contract_documents(root: Path) -> dict[str, Any]:
    _loader_preflight("load_contract_documents", root)
    return _load_implementation().load_contract_documents(root)


def validate_contract_manifest(
    root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    """Validate manifest inventory after preflighting both trust boundaries."""

    facade_errors = _symlink_preflight(ROOT)
    if facade_errors:
        return facade_errors

    errors = _symlink_preflight(root, manifest)
    if errors:
        return errors
    return _load_implementation().validate_contract_manifest(root, manifest)


def __getattr__(name: str) -> Any:
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    preflight_errors = _symlink_preflight(ROOT)
    if preflight_errors:
        if name == "CONTRACT_SCHEMAS":
            return {}
        details = "; ".join(preflight_errors)
        raise RuntimeError(
            f"cannot load validator attribute {name!r} before trust-boundary "
            f"preflight succeeds: {details}"
        )

    root_loaders = {
        "load_contract_manifest": _load_contract_manifest,
        "load_contract_registry": _load_contract_registry,
        "load_contract_documents": _load_contract_documents,
    }
    if name in root_loaders:
        return root_loaders[name]

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


def _path_escapes_root(relative: str) -> bool:
    path = Path(relative)
    return path.is_absolute() or ".." in path.parts


def _manifest_regular_file_error(root: Path) -> str | None:
    manifest_path = root / MANIFEST_PATH
    try:
        mode = manifest_path.lstat().st_mode
    except (FileNotFoundError, OSError):
        return None
    if stat.S_ISLNK(mode):
        return None
    if not stat.S_ISREG(mode):
        return f"{MANIFEST_PATH}: manifest must be a regular file"
    return None


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


def _symlink_preflight(
    root: Path,
    manifest: dict[str, Any] | None = None,
    *,
    check_inventory: bool = True,
) -> list[str]:
    if root.is_symlink():
        return ["repository root must not be a symbolic link"]
    if _path_contains_symlink(root, MANIFEST_PATH):
        return [f"{MANIFEST_PATH}: manifest must not be a symbolic link"]
    if _path_contains_symlink(root, MANIFEST_SCHEMA_PATH):
        return [
            f"{MANIFEST_SCHEMA_PATH}: bootstrap schema must not be a symbolic link"
        ]

    manifest_file_error = _manifest_regular_file_error(root)
    if manifest_file_error:
        return [manifest_file_error]

    directory_errors = _directory_symlink_errors(root)
    if directory_errors:
        return directory_errors

    if manifest is None:
        manifest = _load_manifest_for_preflight(root)
    if manifest is None:
        return []

    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        return []

    errors: list[str] = []
    registered_schemas: set[str] = set()
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        contract_id = entry.get("id")
        rendered_id = contract_id if isinstance(contract_id, str) else "<unknown>"
        schema_path = entry.get("schema")
        if isinstance(schema_path, str):
            registered_schemas.add(schema_path)
        for label in ("document", "schema"):
            relative = entry.get(label)
            if not isinstance(relative, str):
                continue
            if _path_escapes_root(relative):
                errors.append(
                    f"{MANIFEST_PATH}:$.contracts[{entry_index}].{label}: "
                    f"contract manifest {rendered_id}: {label} escapes repository root: "
                    f"{relative}"
                )
                continue
            if _path_contains_symlink(root, relative):
                errors.append(
                    f"contract manifest {rendered_id}: {label} must not be a symbolic link: "
                    f"{relative}"
                )

    if check_inventory:
        actual_schemas = {
            path.relative_to(root).as_posix()
            for path in (root / "schemas").rglob("*.json")
            if path.is_file() or path.is_symlink()
        } - {MANIFEST_SCHEMA_PATH}
        for relative in sorted(actual_schemas - registered_schemas):
            errors.append(f"unregistered contract schema: {relative}")

    return errors


def _document_metadata_errors(root: Path, implementation: ModuleType) -> list[str]:
    try:
        manifest = implementation.load_contract_manifest(root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError):
        return []

    errors: list[str] = []
    for entry in manifest.get("contracts", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("document"), str):
            continue
        document_path = entry["document"]
        candidate = root / document_path
        if not candidate.is_file():
            continue
        try:
            document = implementation.load_json(candidate)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(document, dict):
            errors.append(
                f"{document_path}: registered contract document must be a JSON object "
                "with $schema and schemaVersion metadata"
            )
    return errors


def validate_repository(root: Path) -> list[str]:
    facade_errors = _symlink_preflight(ROOT)
    if facade_errors:
        return facade_errors

    errors = _symlink_preflight(root)
    if errors:
        return errors

    implementation = _load_implementation()
    metadata_errors = _document_metadata_errors(root, implementation)
    if metadata_errors:
        return metadata_errors
    return implementation.validate_repository(root)


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
