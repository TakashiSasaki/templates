#!/usr/bin/env python3
"""Validate the generated contract registry and registered contract documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from contract_common import DuplicateKeyError, NonStandardJsonConstantError, load_json, load_manifest

MANIFEST = "contracts/manifest.json"
MANIFEST_SCHEMA = "schemas/contract-manifest.schema.json"


def _history_errors(entry: dict) -> list[str]:
    errors: list[str] = []
    history = entry["versionHistory"]
    versions = [item["version"] for item in history]
    expected = list(range(1, entry["documentSchemaVersion"] + 1))
    if versions != expected:
        errors.append(f"{entry['id']}: versionHistory must be contiguous from 1 through {entry['documentSchemaVersion']}: got {versions}")
    if history[0] != {"version": 1, "changeType": "initial"}:
        errors.append(f"{entry['id']}: version 1 must be initial")
    for item in history[1:]:
        expected_path = f"docs/migrations/{entry['migrationSlug']}-v{item['version'] - 1}-to-v{item['version']}.md"
        if item.get("migration") != expected_path:
            errors.append(f"{entry['id']}: version {item['version']} migration must be {expected_path}")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_schema_path = root / MANIFEST_SCHEMA
    if manifest_schema_path.is_symlink():
        return [f"{MANIFEST_SCHEMA} must not be a symbolic link"]
    try:
        manifest = load_manifest(root)
        manifest_schema = load_json(manifest_schema_path)
    except (OSError, UnicodeDecodeError, ValueError, TypeError, DuplicateKeyError, NonStandardJsonConstantError) as exc:
        return [f"cannot load contract manifest/bootstrap schema: {exc}"]
    try:
        Draft202012Validator.check_schema(manifest_schema)
        manifest_validation = sorted(Draft202012Validator(manifest_schema).iter_errors(manifest), key=lambda item: tuple(item.absolute_path))
    except Exception as exc:
        return [f"{MANIFEST_SCHEMA}: invalid JSON Schema: {exc}"]
    for error in manifest_validation:
        errors.append(f"{MANIFEST}: {error.message}")
    if errors:
        return errors

    entries = manifest["contracts"]
    ids = [entry["id"] for entry in entries]
    documents = [entry["document"] for entry in entries]
    schemas = [entry["schema"] for entry in entries]
    if ids != sorted(ids):
        errors.append("contracts/manifest.json contracts must be sorted lexically by id")
    for label, values in (("id", ids), ("document", documents), ("schema", schemas)):
        if len(values) != len(set(values)):
            errors.append(f"duplicate contract {label} in manifest")

    expected_docs = {MANIFEST, *documents}
    expected_schemas = {MANIFEST_SCHEMA, *schemas}
    actual_docs = {path.relative_to(root).as_posix() for path in (root / "contracts").glob("*.json") if path.is_file() or path.is_symlink()} if (root / "contracts").is_dir() else set()
    actual_schemas = {path.relative_to(root).as_posix() for path in (root / "schemas").glob("*.schema.json") if path.is_file() or path.is_symlink()} if (root / "schemas").is_dir() else set()
    # Directory membership is not an ownership transfer. A real consumer may
    # already have unrelated schemas, contracts, and migration documents here.
    # Full Composition validation verifies lock structure and digests first;
    # this validator checks registry closure within that provider inventory.
    lock_path = root / ".template-composition/lock.json"
    owned = actual_docs | actual_schemas
    if lock_path.exists() or lock_path.is_symlink():
        try:
            if lock_path.is_symlink():
                raise ValueError("Composition lock must be a regular file")
            lock = load_json(lock_path)
            owned = {item["destination"] for item in lock["files"]}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return errors + [f"cannot establish Composition ownership inventory: {exc}"]
    for extra in sorted((actual_docs & owned) - expected_docs): errors.append(f"unregistered contract document: {extra}")
    for missing in sorted(expected_docs - actual_docs): errors.append(f"missing contract document: {missing}")
    for extra in sorted((actual_schemas & owned) - expected_schemas): errors.append(f"unregistered contract schema: {extra}")
    for missing in sorted(expected_schemas - actual_schemas): errors.append(f"missing contract schema: {missing}")

    registered_migrations: set[str] = set()
    for entry in entries:
        errors.extend(_history_errors(entry))
        for item in entry["versionHistory"][1:]:
            registered_migrations.add(item["migration"])
        for label, relative in (("document", entry["document"]), ("schema", entry["schema"])):
            candidate = root / relative
            if candidate.is_symlink():
                errors.append(f"{entry['id']}: {label} must not be a symbolic link: {relative}")
            elif not candidate.is_file():
                errors.append(f"{entry['id']}: missing {label}: {relative}")
        if not (root / entry["document"]).is_file() or not (root / entry["schema"]).is_file():
            continue
        try:
            document = load_json(root / entry["document"])
            schema = load_json(root / entry["schema"])
        except (OSError, UnicodeDecodeError, ValueError, DuplicateKeyError, NonStandardJsonConstantError) as exc:
            errors.append(f"{entry['id']}: cannot load document/schema: {exc}")
            continue
        if not isinstance(document, dict):
            errors.append(f"{entry['id']}: contract document must be an object")
            continue
        if document.get("$schema") != f"../{entry['schema']}": errors.append(f"{entry['id']}: document $schema does not match manifest")
        if document.get("schemaVersion") != entry["documentSchemaVersion"]: errors.append(f"{entry['id']}: document schemaVersion does not match manifest")
        try:
            Draft202012Validator.check_schema(schema)
            for error in Draft202012Validator(schema).iter_errors(document): errors.append(f"{entry['document']}: {error.message}")
        except Exception as exc:
            errors.append(f"{entry['schema']}: invalid JSON Schema: {exc}")

    migration_root = root / "docs/migrations"
    actual_migrations = {path.relative_to(root).as_posix() for path in migration_root.iterdir() if path.is_file() or path.is_symlink()} if migration_root.is_dir() else set()
    migration_inventory = actual_migrations & owned if lock_path.exists() else actual_migrations
    for extra in sorted(migration_inventory - registered_migrations): errors.append(f"unregistered migration artifact: {extra}")
    for missing in sorted(registered_migrations - actual_migrations): errors.append(f"missing migration artifact: {missing}")
    for relative in sorted(registered_migrations & actual_migrations):
        candidate = root / relative
        if candidate.is_symlink():
            errors.append(f"registered migration must not be a symbolic link: {relative}")
        elif not candidate.is_file():
            errors.append(f"registered migration must be a regular file: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Contract evolution validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
