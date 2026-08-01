#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

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


def _symlink_preflight(root: Path) -> list[str]:
    if _path_contains_symlink(root, _impl.MANIFEST_PATH):
        return [
            f"{_impl.MANIFEST_PATH}: manifest must not be a symbolic link"
        ]

    try:
        manifest = _impl.load_contract_manifest(root)
    except _impl._load_json_error_types():
        return []

    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        return []

    errors: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        contract_id = entry.get("id")
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
    return errors


def validate_repository(root: Path) -> list[str]:
    errors = _symlink_preflight(root)
    if errors:
        return errors
    return _impl.validate_repository(root)


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
