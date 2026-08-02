#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

MANIFEST_PATH = "contracts/manifest.json"
MANIFEST_SCHEMA_PATH = "schemas/contract-manifest.schema.json"
ROOT = Path(__file__).resolve().parents[1]

_SCHEMA_SINGLE_KEYWORDS = {
    "additionalItems",
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
}
_SCHEMA_ARRAY_KEYWORDS = {"allOf", "anyOf", "oneOf", "prefixItems"}
_SCHEMA_MAP_KEYWORDS = {
    "$defs",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
}

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
    """Load only the implementation file adjacent to this verified facade."""

    global _IMPLEMENTATION
    if _IMPLEMENTATION is not None:
        return _IMPLEMENTATION

    implementation_path = Path(__file__).resolve().with_name(
        "validate_contracts_impl.py"
    )
    try:
        mode = implementation_path.lstat().st_mode
    except OSError as exc:
        raise RuntimeError(
            f"cannot inspect validator implementation: {implementation_path}: {exc}"
        ) from exc
    if not stat.S_ISREG(mode):
        raise RuntimeError(
            "validator implementation must be a regular sibling file: "
            f"{implementation_path}"
        )

    module_name = (
        f"{__package__}.validate_contracts_impl"
        if __package__
        else "validate_contracts_impl"
    )
    existing = sys.modules.get(module_name)
    if existing is not None:
        existing_file = getattr(existing, "__file__", None)
        if existing_file is not None:
            try:
                if Path(existing_file).resolve() == implementation_path:
                    _IMPLEMENTATION = existing
                    return existing
            except (OSError, RuntimeError):
                pass

    spec = importlib.util.spec_from_file_location(module_name, implementation_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"cannot create import specification for {implementation_path}"
        )
    implementation = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = implementation
    try:
        spec.loader.exec_module(implementation)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise

    _IMPLEMENTATION = implementation
    return implementation


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


def _non_regular_file(root: Path, relative: str) -> bool:
    try:
        mode = (root / relative).lstat().st_mode
    except (FileNotFoundError, OSError):
        return False
    return not stat.S_ISLNK(mode) and not stat.S_ISREG(mode)


def _root_resolution_error(root: Path) -> str | None:
    try:
        root.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        return f"repository root path cannot be resolved safely: {exc}"
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


def _reference_error(reference: str, schema_path: str) -> str | None:
    try:
        parsed = urlsplit(reference)
    except ValueError as exc:
        return (
            f"{schema_path}: invalid JSON Schema reference URI: "
            f"{reference!r}: {exc}"
        )
    if parsed.scheme or parsed.netloc or parsed.path or parsed.query:
        return (
            f"{schema_path}: external JSON Schema reference is not allowed: "
            f"{reference!r}"
        )
    return None


def _external_reference_errors(
    value: Any,
    schema_path: str,
) -> list[str]:
    """Inspect only locations whose values are JSON Schemas."""

    errors: list[str] = []

    def visit_schema(schema: Any) -> None:
        if isinstance(schema, bool) or not isinstance(schema, dict):
            return

        for keyword in ("$ref", "$dynamicRef"):
            reference = schema.get(keyword)
            if isinstance(reference, str):
                error = _reference_error(reference, schema_path)
                if error is not None:
                    errors.append(error)

        for keyword in _SCHEMA_SINGLE_KEYWORDS:
            child = schema.get(keyword)
            if isinstance(child, (dict, bool)):
                visit_schema(child)
            elif keyword in {"additionalItems", "items"} and isinstance(child, list):
                for item in child:
                    visit_schema(item)

        for keyword in _SCHEMA_ARRAY_KEYWORDS:
            children = schema.get(keyword)
            if isinstance(children, list):
                for child in children:
                    visit_schema(child)

        for keyword in _SCHEMA_MAP_KEYWORDS:
            children = schema.get(keyword)
            if isinstance(children, dict):
                for child in children.values():
                    visit_schema(child)

        dependencies = schema.get("dependencies")
        if isinstance(dependencies, dict):
            for child in dependencies.values():
                if isinstance(child, (dict, bool)):
                    visit_schema(child)

    visit_schema(value)
    return errors


def _schema_reference_errors(root: Path, relative: str) -> list[str]:
    if _path_escapes_root(relative):
        return []
    if _path_contains_symlink(root, relative) or _non_regular_file(root, relative):
        return []
    try:
        with (root / relative).open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return _external_reference_errors(schema, relative)


def _symlink_preflight(
    root: Path,
    manifest: dict[str, Any] | None = None,
    *,
    check_inventory: bool = True,
) -> list[str]:
    if root.is_symlink():
        return ["repository root must not be a symbolic link"]
    root_error = _root_resolution_error(root)
    if root_error:
        return [root_error]
    if _path_contains_symlink(root, MANIFEST_PATH):
        return [f"{MANIFEST_PATH}: manifest must not be a symbolic link"]
    if _path_contains_symlink(root, MANIFEST_SCHEMA_PATH):
        return [
            f"{MANIFEST_SCHEMA_PATH}: bootstrap schema must not be a symbolic link"
        ]
    if _non_regular_file(root, MANIFEST_PATH):
        return [f"{MANIFEST_PATH}: manifest must be a regular file"]
    if _non_regular_file(root, MANIFEST_SCHEMA_PATH):
        return [f"{MANIFEST_SCHEMA_PATH}: bootstrap schema must be a regular file"]

    directory_errors = _directory_symlink_errors(root)
    if directory_errors:
        return directory_errors

    errors = _schema_reference_errors(root, MANIFEST_SCHEMA_PATH)

    if manifest is None:
        manifest = _load_manifest_for_preflight(root)
    if manifest is None:
        return errors

    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        return errors

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
                continue
            if _non_regular_file(root, relative):
                errors.append(
                    f"contract manifest {rendered_id}: {label} must be a regular file: "
                    f"{relative}"
                )

    for relative in sorted(registered_schemas):
        errors.extend(_schema_reference_errors(root, relative))

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
