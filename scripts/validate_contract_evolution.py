#!/usr/bin/env python3
"""Validate contract version histories and migration-document inventory."""

from __future__ import annotations

import json
import os
import stat
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    from scripts import validate_contracts
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    import validate_contracts  # type: ignore[no-redef]

MIGRATIONS_DIRECTORY = "docs/migrations"
RESERVED_BOOTSTRAP_MIGRATION_SLUG = "contract-manifest"


def _unresolved_absolute(path: str | Path) -> Path:
    """Return an absolute path without resolving symbolic links."""

    return Path(os.path.abspath(os.fspath(path)))


def _invocation_root() -> Path:
    """Preserve a symlinked CLI invocation path for root preflight."""

    file_root = _unresolved_absolute(__file__).parents[1]
    pwd_value = os.environ.get("PWD")
    if not pwd_value:
        return file_root

    pwd = Path(pwd_value)
    if not pwd.is_absolute():
        return file_root

    candidate = pwd / "scripts" / Path(__file__).name
    try:
        if candidate.exists() and os.path.samefile(candidate, __file__):
            return pwd
    except OSError:
        pass
    return file_root


ROOT = _invocation_root()


def _duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _has_visible_character(value: str) -> bool:
    return any(
        character not in validate_contracts.VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def _root_symlink_error(root: Path) -> str | None:
    """Reject a symbolic link at any component of the unresolved root path."""

    absolute = _unresolved_absolute(root)
    candidate = Path(absolute.anchor) if absolute.anchor else Path()
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts

    for part in parts:
        candidate /= part
        try:
            is_symlink = candidate.is_symlink()
        except (OSError, ValueError) as exc:
            return f"repository root path cannot be inspected safely: {exc}"
        if not is_symlink:
            continue
        if candidate == absolute:
            return "repository root must not be a symbolic link"
        return "repository root path must not contain symbolic links"
    return None


def _first_symlink_component(root: Path, relative: str) -> str | None:
    path = Path(relative)
    if path.is_absolute():
        return None

    candidate = root
    traversed: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        candidate /= part
        traversed.append(part)
        if candidate.is_symlink():
            return Path(*traversed).as_posix()
    return None


def _path_contains_symlink(root: Path, relative: str) -> bool:
    return _first_symlink_component(root, relative) is not None


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


def _migration_directory_symlink_errors(root: Path) -> list[str]:
    symlink_component = _first_symlink_component(root, MIGRATIONS_DIRECTORY)
    if symlink_component == MIGRATIONS_DIRECTORY:
        return [
            f"{MIGRATIONS_DIRECTORY}: migration directory must not be a symbolic link"
        ]
    if symlink_component is not None:
        return [
            f"{MIGRATIONS_DIRECTORY}: migration path must not contain symbolic links"
        ]

    migrations_root = root / MIGRATIONS_DIRECTORY
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


def _validate_migration_content(
    root: Path,
    *,
    owner: str,
    migration: str,
) -> list[str]:
    try:
        content = (root / migration).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{owner}: unable to read migration {migration}: {exc}"]
    if not _has_visible_character(content):
        return [
            f"{owner}: migration must contain at least one visible character: {migration}"
        ]
    return []


def _history_is_contiguous(
    current_version: int,
    history: list[dict[str, Any]],
) -> bool:
    if current_version < 1 or len(history) != current_version:
        return False
    return all(
        isinstance(entry, dict) and entry.get("version") == expected_version
        for expected_version, entry in enumerate(history, start=1)
    )


def _validate_version_history(
    root: Path,
    *,
    owner: str,
    migration_slug: str,
    current_version: int,
    history: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    migrations: list[str] = []

    if not _history_is_contiguous(current_version, history):
        errors.append(
            f"{owner}: versionHistory must contain contiguous versions "
            f"1 through {current_version}"
        )

    for transition in history[1:]:
        version = transition["version"]
        migration = transition["migration"]
        migrations.append(migration)
        expected = (
            f"{MIGRATIONS_DIRECTORY}/{migration_slug}-v{version - 1}-to-v{version}.md"
        )
        if migration != expected:
            errors.append(
                f"{owner}: version {version} migration must be {expected}"
            )

        try:
            if _path_escapes_root(migration):
                errors.append(
                    f"{owner}: migration escapes repository root: {migration}"
                )
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
                continue
            errors.extend(
                _validate_migration_content(
                    root,
                    owner=owner,
                    migration=migration,
                )
            )
        except ValueError as exc:
            errors.append(f"{owner}: invalid migration path {migration!r}: {exc}")

    return errors, migrations


def _evolution_metadata(
    manifest: dict[str, Any],
) -> tuple[
    int,
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    schema_version = manifest["schemaVersion"]
    history = manifest["versionHistory"]
    contracts = manifest["contracts"]
    retired_contracts = manifest["retiredContracts"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise TypeError("schemaVersion must be an integer")
    if not isinstance(history, list):
        raise TypeError("versionHistory must be an array")
    if not isinstance(contracts, list):
        raise TypeError("contracts must be an array")
    if not isinstance(retired_contracts, list):
        raise TypeError("retiredContracts must be an array")
    return schema_version, history, contracts, retired_contracts


def _validate_entry_identity_inventory(
    contracts: list[dict[str, Any]],
    retired_contracts: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []

    for prefix, entries in (
        ("contract manifest", contracts),
        ("retired contract manifest", retired_contracts),
    ):
        for entry in entries:
            owner = f"{prefix} {entry['id']}"
            if entry["migrationSlug"] == RESERVED_BOOTSTRAP_MIGRATION_SLUG:
                errors.append(
                    f"{owner}: migrationSlug "
                    f"{RESERVED_BOOTSTRAP_MIGRATION_SLUG} is reserved for "
                    "the manifest bootstrap"
                )
            if entry["document"] == validate_contracts.MANIFEST_PATH:
                errors.append(
                    f"{owner}: document must not claim bootstrap path "
                    f"{validate_contracts.MANIFEST_PATH}"
                )
            if entry["schema"] == validate_contracts.MANIFEST_SCHEMA_PATH:
                errors.append(
                    f"{owner}: schema must not claim bootstrap path "
                    f"{validate_contracts.MANIFEST_SCHEMA_PATH}"
                )

    entries = contracts + retired_contracts
    for label, key in (
        ("contract id", "id"),
        ("contract document", "document"),
        ("contract schema", "schema"),
        ("migration slug", "migrationSlug"),
    ):
        values = [entry[key] for entry in entries]
        for duplicate in sorted(_duplicate_values(values)):
            errors.append(f"duplicate active or retired {label}: {duplicate}")
    return errors


def _validate_retired_contract(
    root: Path,
    entry: dict[str, Any],
) -> tuple[list[str], list[str]]:
    contract_id = entry["id"]
    owner = f"retired contract manifest {contract_id}"
    last_document_version = entry["lastDocumentSchemaVersion"]
    retired_version = entry["retiredVersion"]
    history = entry["versionHistory"]
    purpose = entry["purpose"]
    errors: list[str] = []

    if not isinstance(purpose, str):
        raise TypeError(f"{owner} purpose must be a string")
    if not _has_visible_character(purpose):
        errors.append(
            f"{owner}: purpose must contain at least one visible character"
        )

    if retired_version != last_document_version + 1:
        errors.append(
            f"{owner}: retiredVersion must equal lastDocumentSchemaVersion plus 1"
        )
    if history and not isinstance(history[-1], dict):
        raise TypeError(f"{owner} final versionHistory entry must be an object")
    if not history or history[-1].get("changeType") != "breaking":
        errors.append(f"{owner}: retirement transition must be breaking")

    history_errors, migrations = _validate_version_history(
        root,
        owner=owner,
        migration_slug=entry["migrationSlug"],
        current_version=retired_version,
        history=history,
    )
    errors.extend(history_errors)
    return errors, migrations


def validate_contract_evolution(
    root: Path,
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Validate contiguous version histories and the closed migration inventory."""

    root_symlink_error = _root_symlink_error(root)
    if root_symlink_error:
        return [root_symlink_error]
    root_error = _root_resolution_error(root)
    if root_error:
        return [root_error]

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
            RuntimeError,
        ) as exc:
            return [
                f"{validate_contracts.MANIFEST_PATH}: unable to load JSON: {exc}"
            ]

    try:
        (
            schema_version,
            manifest_history,
            contracts,
            retired_contracts,
        ) = _evolution_metadata(manifest)
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
        errors.extend(
            _validate_entry_identity_inventory(contracts, retired_contracts)
        )

        history_errors, migrations = _validate_version_history(
            root,
            owner="contract manifest bootstrap",
            migration_slug=RESERVED_BOOTSTRAP_MIGRATION_SLUG,
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
                migration_slug=entry["migrationSlug"],
                current_version=entry["documentSchemaVersion"],
                history=entry["versionHistory"],
            )
            errors.extend(history_errors)
            registered_migrations.extend(migrations)

        for entry in retired_contracts:
            retirement_errors, migrations = _validate_retired_contract(
                root, entry
            )
            errors.extend(retirement_errors)
            registered_migrations.extend(migrations)
    except (KeyError, TypeError, AttributeError) as exc:
        errors.append(
            f"{validate_contracts.MANIFEST_PATH}: evolution metadata is incomplete or malformed: {exc}"
        )
        return errors

    for duplicate in sorted(_duplicate_values(registered_migrations)):
        errors.append(f"duplicate migration document: {duplicate}")

    migrations_root = root / MIGRATIONS_DIRECTORY
    actual_migrations: set[str] = set()
    if migrations_root.is_dir():
        for path in migrations_root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                continue
            actual_migrations.add(path.relative_to(root).as_posix())

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
