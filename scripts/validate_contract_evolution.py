#!/usr/bin/env python3
"""Validate contract version histories and migration-document inventory."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

try:
    from scripts import validate_contracts
except ModuleNotFoundError:
    import validate_contracts  # type: ignore[no-redef]

MIGRATIONS_DIRECTORY = "docs/migrations"
ROOT = Path(__file__).resolve().parents[1]


def _duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


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


def _migration_directory_symlink_errors(root: Path) -> list[str]:
    migrations_root = root / MIGRATIONS_DIRECTORY
    if migrations_root.is_symlink():
        return [
            f"{MIGRATIONS_DIRECTORY}: migration directory must not be a symbolic link"
        ]
    if not migrations_root.is_dir():
        return []

    errors: list[str] = []
    for current, directory_names, _ in os.walk(
        migrations_root, followlinks=False
    ):
        current_path = Path(current)
        for name in directory_names:
            candidate = current_path / name
            if candidate.is_symlink():
                relative = candidate.relative_to(root).as_posix()
                errors.append(
                    f"{relative}: migration directory must not be a symbolic link"
                )
    return errors


def _validate_version_history(
    root: Path,
    *,
    owner: str,
    slug: str,
    current_version: int,
    history: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    migrations: list[str] = []

    expected_versions = list(range(1, current_version + 1))
    actual_versions = [entry["version"] for entry in history]
    if actual_versions != expected_versions:
        errors.append(
            f"{owner}: versionHistory must contain contiguous versions "
            f"1 through {current_version}"
        )

    for transition in history[1:]:
        version = transition["version"]
        migration = transition["migration"]
        migrations.append(migration)
        expected = (
            f"{MIGRATIONS_DIRECTORY}/{slug}-v{version - 1}-to-v{version}.md"
        )
        if migration != expected:
            errors.append(
                f"{owner}: version {version} migration must be {expected}"
            )

        if _path_escapes_root(migration):
            errors.append(f"{owner}: migration escapes repository root: {migration}")
            continue
        if _path_contains_symlink(root, migration):
            errors.append(
                f"{owner}: migration must not be a symbolic link: {migration}"
            )
            continue
        if _non_regular_file(root, migration):
            errors.append(
                f"{owner}: migration must be a regular file: {migration}"
            )
            continue
        candidate = root / migration
        if not candidate.is_file():
            errors.append(f"{owner}: missing migration: {migration}")

    return errors, migrations


def _evolution_metadata(
    manifest: dict[str, Any],
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    schema_version = manifest["schemaVersion"]
    history = manifest["versionHistory"]
    contracts = manifest["contracts"]
    if not isinstance(schema_version, int):
        raise TypeError("schemaVersion must be an integer")
    if not isinstance(history, list):
        raise TypeError("versionHistory must be an array")
    if not isinstance(contracts, list):
        raise TypeError("contracts must be an array")
    return schema_version, history, contracts


def validate_contract_evolution(
    root: Path,
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Validate contiguous version histories and the closed migration inventory."""

    if manifest is None:
        try:
            manifest = validate_contracts.load_contract_manifest(root)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            return [
                f"{validate_contracts.MANIFEST_PATH}: unable to load JSON: {exc}"
            ]

    try:
        schema_version, manifest_history, contracts = _evolution_metadata(manifest)
    except (KeyError, TypeError) as exc:
        return [
            f"{validate_contracts.MANIFEST_PATH}: evolution metadata is incomplete or malformed: {exc}"
        ]

    directory_errors = _migration_directory_symlink_errors(root)
    if directory_errors:
        return directory_errors

    errors: list[str] = []
    registered_migrations: list[str] = []

    try:
        history_errors, migrations = _validate_version_history(
            root,
            owner="contract manifest bootstrap",
            slug="contract-manifest",
            current_version=schema_version,
            history=manifest_history,
        )
        errors.extend(history_errors)
        registered_migrations.extend(migrations)

        for entry in contracts:
            contract_id = entry["id"]
            history_errors, migrations = _validate_version_history(
                root,
                owner=f"contract manifest {contract_id}",
                slug=Path(entry["document"]).stem,
                current_version=entry["documentSchemaVersion"],
                history=entry["versionHistory"],
            )
            errors.extend(history_errors)
            registered_migrations.extend(migrations)
    except (KeyError, TypeError) as exc:
        errors.append(
            f"{validate_contracts.MANIFEST_PATH}: evolution metadata is incomplete or malformed: {exc}"
        )
        return errors

    for duplicate in sorted(_duplicate_values(registered_migrations)):
        errors.append(f"duplicate migration document: {duplicate}")

    migrations_root = root / MIGRATIONS_DIRECTORY
    actual_migrations = (
        {
            path.relative_to(root).as_posix()
            for path in migrations_root.rglob("*.md")
            if path.is_file() or path.is_symlink() or _non_regular_file(root, path.relative_to(root).as_posix())
        }
        if migrations_root.is_dir()
        else set()
    )
    for relative in sorted(actual_migrations - set(registered_migrations)):
        errors.append(f"unregistered migration document: {relative}")

    return errors


def main() -> int:
    errors = validate_contract_evolution(ROOT)
    if errors:
        print("Contract evolution validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All contract version histories and migrations are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
