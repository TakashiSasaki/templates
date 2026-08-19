#!/usr/bin/env python3
"""Enforce monotonic component versions when descriptor bytes change."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ComponentVersionGuardError(ValueError):
    pass


def _run_git(root: Path, *arguments: str, allow_failure: bool = False) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 and not allow_failure:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ComponentVersionGuardError(
            f"git {' '.join(arguments)} failed with exit code {result.returncode}: {message}"
        )
    return result


def _descriptor_identity(data: bytes, *, label: str) -> tuple[str, int]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComponentVersionGuardError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ComponentVersionGuardError(f"{label} must contain a JSON object")
    component_id = value.get("id")
    version = value.get("version")
    if not isinstance(component_id, str) or not component_id:
        raise ComponentVersionGuardError(f"{label} has an invalid component id")
    if type(version) is not int or version < 1:
        raise ComponentVersionGuardError(f"{label} has an invalid positive integer version")
    return component_id, version


def validate_descriptor_transition(old_bytes: bytes, new_bytes: bytes, *, path: str) -> None:
    if old_bytes == new_bytes:
        return
    old_id, old_version = _descriptor_identity(old_bytes, label=f"old {path}")
    new_id, new_version = _descriptor_identity(new_bytes, label=f"new {path}")
    if old_id != new_id:
        raise ComponentVersionGuardError(
            f"component id changed in place at {path}: {old_id!r} -> {new_id!r}"
        )
    if new_version <= old_version:
        raise ComponentVersionGuardError(
            "component descriptor bytes changed without a strict version increase: "
            f"{old_id} v{old_version} -> v{new_version} ({path})"
        )


def _base_descriptor_bytes(root: Path, base_revision: str, relative_path: str) -> bytes | None:
    listing = _run_git(
        root,
        "ls-tree",
        "--name-only",
        base_revision,
        "--",
        relative_path,
    ).stdout.decode("utf-8", errors="strict").strip()
    if not listing:
        return None
    if listing != relative_path:
        raise ComponentVersionGuardError(
            f"unexpected base tree entry while reading {relative_path}: {listing!r}"
        )
    return _run_git(root, "show", f"{base_revision}:{relative_path}").stdout


def validate_repository(base_revision: str, *, root: Path = ROOT) -> int:
    root = root.resolve()
    _run_git(root, "cat-file", "-e", f"{base_revision}^{{commit}}")
    ancestry = _run_git(
        root,
        "merge-base",
        "--is-ancestor",
        base_revision,
        "HEAD",
        allow_failure=True,
    )
    if ancestry.returncode != 0:
        raise ComponentVersionGuardError(
            f"comparison base {base_revision} is not an ancestor of HEAD"
        )

    errors: list[str] = []
    compared = 0
    component_root = root / "components"
    for descriptor_path in sorted(component_root.glob("*/component.json")):
        relative_path = descriptor_path.relative_to(root).as_posix()
        old_bytes = _base_descriptor_bytes(root, base_revision, relative_path)
        if old_bytes is None:
            continue
        compared += 1
        try:
            validate_descriptor_transition(
                old_bytes,
                descriptor_path.read_bytes(),
                path=relative_path,
            )
        except ComponentVersionGuardError as exc:
            errors.append(str(exc))

    if errors:
        raise ComponentVersionGuardError("\n".join(errors))
    return compared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="ancestor revision to compare against")
    args = parser.parse_args()
    try:
        compared = validate_repository(args.base)
    except (ComponentVersionGuardError, UnicodeDecodeError) as exc:
        print(f"component version guard failed:\n{exc}", file=sys.stderr)
        return 2
    print(f"component version guard passed for {compared} existing component descriptors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
