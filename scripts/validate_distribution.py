#!/usr/bin/env python3
"""Validate the closed, byte-preserving Webapp template distribution."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "distribution-manifest.json"
_ALLOWED_MANIFEST_KEYS = {
    "schema_version",
    "source_root",
    "destination_root",
    "content_transformation_allowed",
    "required_top_level_entries",
    "mirrors",
    "distribution_owned_files",
    "forbidden_distribution_paths",
}
_ALLOWED_MIRROR_KEYS = {"source", "destination", "exclude"}


class DistributionValidationError(ValueError):
    """Raised when the source-to-distribution boundary is invalid."""


def fail(message: str) -> None:
    raise DistributionValidationError(message)


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            fail(f"distribution manifest: duplicate JSON member {key}")
        value[key] = member
    return value


def _load_manifest() -> dict[str, Any]:
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_members)
    except (OSError, json.JSONDecodeError) as error:
        fail(f"distribution manifest: cannot read valid JSON: {error}")
    if not isinstance(value, dict):
        fail("distribution manifest: root must be an object")
    unknown = set(value) - _ALLOWED_MANIFEST_KEYS
    missing = _ALLOWED_MANIFEST_KEYS - set(value)
    if unknown:
        fail(f"distribution manifest: unsupported members: {sorted(unknown)}")
    if missing:
        fail(f"distribution manifest: missing members: {sorted(missing)}")
    return value


def _safe_relative_path(value: Any, context: str, *, allow_dot: bool = False) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{context}: path must be a non-empty string")
    if value == "." and allow_dot:
        return value
    if "\\" in value or ":" in value:
        fail(f"{context}: path is not portable: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        fail(f"{context}: path must be normalized and relative: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        fail(f"{context}: dot or empty path component is prohibited: {value}")
    if any(part.lower() == ".git" for part in path.parts):
        fail(f"{context}: .git path component is prohibited: {value}")
    return value


def _string_list(value: Any, context: str) -> list[str]:
    if not isinstance(value, list):
        fail(f"{context}: value must be an array")
    paths = [_safe_relative_path(item, context) for item in value]
    if paths != sorted(paths):
        fail(f"{context}: paths must be sorted")
    if len(paths) != len(set(paths)):
        fail(f"{context}: duplicate path")
    return paths


def _git_tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(
            "distribution validation requires a Git checkout: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    files: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            fail(f"tracked path is not UTF-8: {error}")
        _safe_relative_path(path, "tracked file")
        files.add(path)
    return files


def _reject_symbolic_or_nonregular(path_text: str, context: str) -> None:
    path = ROOT / path_text
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        fail(f"{context}: cannot inspect {path_text}: {error}")
    if stat.S_ISLNK(mode):
        fail(f"{context}: symbolic links are prohibited: {path_text}")
    if not stat.S_ISREG(mode):
        fail(f"{context}: tracked path is not a regular file: {path_text}")


def _join(destination: str, relative: str) -> str:
    if not relative:
        return destination
    return f"{destination}/{relative}"


def validate_distribution() -> None:
    manifest = _load_manifest()
    if manifest["schema_version"] != 1 or isinstance(
        manifest["schema_version"], bool
    ):
        fail("distribution manifest: schema_version must be integer 1")
    source_root = _safe_relative_path(
        manifest["source_root"], "distribution manifest source_root"
    )
    destination_root = _safe_relative_path(
        manifest["destination_root"],
        "distribution manifest destination_root",
        allow_dot=True,
    )
    if source_root != "template":
        fail("distribution manifest: source_root must be template")
    if destination_root != ".":
        fail("distribution manifest: destination_root must be .")
    if manifest["content_transformation_allowed"] is not False:
        fail("distribution manifest: content transformation must remain disabled")

    required_top_level = _string_list(
        manifest["required_top_level_entries"],
        "distribution manifest required_top_level_entries",
    )
    distribution_owned = _string_list(
        manifest["distribution_owned_files"],
        "distribution manifest distribution_owned_files",
    )
    forbidden = _string_list(
        manifest["forbidden_distribution_paths"],
        "distribution manifest forbidden_distribution_paths",
    )

    tracked = _git_tracked_files()
    template_prefix = f"{source_root}/"
    actual_distribution = {
        path[len(template_prefix) :]
        for path in tracked
        if path.startswith(template_prefix)
    }
    if not actual_distribution:
        fail("distribution: template contains no tracked files")
    for relative in sorted(actual_distribution):
        _safe_relative_path(relative, "distribution tracked file")
        _reject_symbolic_or_nonregular(
            f"{source_root}/{relative}", "distribution tracked file"
        )

    mirrors = manifest["mirrors"]
    if not isinstance(mirrors, list) or not mirrors:
        fail("distribution manifest: mirrors must be a non-empty array")

    expected: set[str] = set(distribution_owned)
    byte_pairs: list[tuple[str, str]] = []
    mirror_sources: set[str] = set()
    mirror_destinations: set[str] = set()

    for index, mirror in enumerate(mirrors):
        context = f"distribution manifest mirrors[{index}]"
        if not isinstance(mirror, dict):
            fail(f"{context}: value must be an object")
        unknown = set(mirror) - _ALLOWED_MIRROR_KEYS
        missing = _ALLOWED_MIRROR_KEYS - set(mirror)
        if unknown or missing:
            fail(
                f"{context}: invalid members; missing={sorted(missing)}, "
                f"unsupported={sorted(unknown)}"
            )
        source = _safe_relative_path(mirror["source"], f"{context} source")
        destination = _safe_relative_path(
            mirror["destination"], f"{context} destination"
        )
        excludes = _string_list(mirror["exclude"], f"{context} exclude")
        if source in mirror_sources:
            fail(f"{context}: duplicate mirror source {source}")
        if destination in mirror_destinations:
            fail(f"{context}: duplicate mirror destination {destination}")
        mirror_sources.add(source)
        mirror_destinations.add(destination)

        source_path = ROOT / source
        if source_path.is_symlink():
            fail(f"{context}: source may not be a symbolic link: {source}")
        if source_path.is_file():
            if excludes:
                fail(f"{context}: a file mirror may not declare exclusions")
            if source not in tracked:
                fail(f"{context}: source file is not tracked: {source}")
            relative_sources = [(source, "")]
        elif source_path.is_dir():
            prefix = f"{source}/"
            source_members = sorted(
                path for path in tracked if path.startswith(prefix)
            )
            if not source_members:
                fail(f"{context}: source directory has no tracked files: {source}")
            relative_sources = [
                (path, path[len(prefix) :])
                for path in source_members
                if path[len(prefix) :] not in excludes
            ]
            available_relatives = {path[len(prefix) :] for path in source_members}
            missing_excludes = sorted(set(excludes) - available_relatives)
            if missing_excludes:
                fail(f"{context}: exclusions are not tracked: {missing_excludes}")
        else:
            fail(f"{context}: source does not exist as a file or directory: {source}")

        for source_file, relative in relative_sources:
            _reject_symbolic_or_nonregular(source_file, context)
            destination_file = _join(destination, relative)
            _safe_relative_path(destination_file, f"{context} mapped destination")
            if destination_file in expected:
                fail(f"{context}: distribution destination collision: {destination_file}")
            expected.add(destination_file)
            byte_pairs.append((source_file, f"{source_root}/{destination_file}"))

    overlap = sorted(set(distribution_owned) & set(forbidden))
    if overlap:
        fail(f"distribution manifest: owned and forbidden paths overlap: {overlap}")

    missing = sorted(expected - actual_distribution)
    undeclared = sorted(actual_distribution - expected)
    if missing:
        fail(f"distribution: declared files are missing: {missing}")
    if undeclared:
        fail(f"distribution: undeclared files are present: {undeclared}")

    present_forbidden = sorted(set(forbidden) & actual_distribution)
    if present_forbidden:
        fail(f"distribution: maintainer-only paths are present: {present_forbidden}")

    actual_top_level = sorted({PurePosixPath(path).parts[0] for path in actual_distribution})
    if actual_top_level != required_top_level:
        fail(
            "distribution: top-level inventory differs; "
            f"expected={required_top_level}, actual={actual_top_level}"
        )

    for owned in distribution_owned:
        _reject_symbolic_or_nonregular(f"{source_root}/{owned}", "distribution-owned file")

    for source_file, destination_file in byte_pairs:
        try:
            source_bytes = (ROOT / source_file).read_bytes()
            destination_bytes = (ROOT / destination_file).read_bytes()
        except OSError as error:
            fail(f"distribution: cannot compare mirrored bytes: {error}")
        if source_bytes != destination_bytes:
            fail(
                "distribution: mirrored bytes differ: "
                f"{source_file} -> {destination_file}"
            )

    print(
        "distribution validation passed: "
        f"{len(actual_distribution)} files, {len(byte_pairs)} byte-preserving mirrors"
    )


def main() -> int:
    try:
        validate_distribution()
    except DistributionValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
