#!/usr/bin/env python3
"""Validate the closed canonical Skill distribution under template/."""

from __future__ import annotations

import json
import os
import posixpath
import subprocess
import sys
from pathlib import Path, PurePosixPath

MANIFEST_KEYS = {
    "schema_version",
    "source_root",
    "destination_root",
    "content_transformation_allowed",
    "required_top_level_entries",
    "distribution_files",
    "forbidden_distribution_paths",
}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def safe_relative_path(value: object, context: str, *, allow_dot: bool = False) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{context}: path must be a non-empty string")
    if allow_dot and value == ".":
        return value
    if "\\" in value or ":" in value:
        fail(f"{context}: path is not portable: {value}")

    path = PurePosixPath(value)
    clean = posixpath.normpath(value)
    if path.is_absolute() or clean != value or any(
        part in {"", ".."} for part in path.parts
    ):
        fail(f"{context}: path must be normalized and relative: {value}")
    if any(part.lower() == ".git" for part in path.parts):
        fail(f"{context}: .git path component is prohibited: {value}")
    return value


def sorted_path_list(value: object, context: str) -> list[str]:
    if not isinstance(value, list):
        fail(f"{context}: value must be an array")
    paths = [safe_relative_path(entry, context) for entry in value]
    if paths != sorted(paths):
        fail(f"{context}: paths must be sorted")
    if len(paths) != len(set(paths)):
        fail(f"{context}: duplicate path")
    return paths


def load_manifest(root: Path) -> dict[str, object]:
    path = root / "distribution-manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"distribution manifest: cannot read valid JSON: {exc}")
    if not isinstance(value, dict):
        fail("distribution manifest: root must be an object")
    unknown = set(value) - MANIFEST_KEYS
    missing = MANIFEST_KEYS - set(value)
    if unknown:
        fail(f"distribution manifest: unsupported members: {sorted(unknown)!r}")
    if missing:
        fail(f"distribution manifest: missing members: {sorted(missing)!r}")
    return value


def tracked_entries(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(name, None)
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--stage", "-z"],
            check=False,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError as exc:
        fail(f"distribution validation requires Git: {exc}")
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"distribution validation requires a Git checkout: {stderr}")

    entries: dict[str, str] = {}
    for raw_record in completed.stdout.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata_raw, path_raw = raw_record.split(b"\t", 1)
            metadata = metadata_raw.decode("ascii")
            path = path_raw.decode("utf-8")
        except (ValueError, UnicodeError):
            fail("tracked entry has an invalid index record")
        parts = metadata.split(" ", 2)
        if len(parts) != 3:
            fail("tracked entry has an invalid index record")
        mode, _sha, stage = parts
        if stage != "0":
            fail(f"tracked entry uses a nonzero index stage: {path}")
        safe_relative_path(path, "tracked file")
        if path in entries:
            fail(f"tracked path appears more than once: {path}")
        entries[path] = mode
    return entries


def descendant(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def validate(root_path: str | os.PathLike[str] = ".") -> bool:
    root = Path(root_path).resolve()
    if not root.is_dir():
        fail(f"source root is not a directory: {root}")

    manifest = load_manifest(root)
    schema_version = manifest["schema_version"]
    if type(schema_version) is not int or schema_version != 2:
        fail("distribution manifest: schema_version must be integer 2")

    source_root = safe_relative_path(
        manifest["source_root"], "distribution manifest source_root"
    )
    destination_root = safe_relative_path(
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

    required_top_level = sorted_path_list(
        manifest["required_top_level_entries"],
        "distribution manifest required_top_level_entries",
    )
    distribution_files = sorted_path_list(
        manifest["distribution_files"], "distribution manifest distribution_files"
    )
    forbidden = sorted_path_list(
        manifest["forbidden_distribution_paths"],
        "distribution manifest forbidden_distribution_paths",
    )

    tracked = tracked_entries(root)
    prefix = source_root + "/"
    actual = {
        path[len(prefix) :]: mode
        for path, mode in tracked.items()
        if path.startswith(prefix)
    }
    if not actual:
        fail("distribution: template contains no tracked files")

    missing_on_disk = sorted(
        relative
        for relative in actual
        if not (root / source_root / relative).exists()
        and not (root / source_root / relative).is_symlink()
    )
    if missing_on_disk:
        fail(f"distribution: declared files are missing: {missing_on_disk!r}")

    for relative, mode in actual.items():
        path = root / source_root / relative
        if mode == "120000" or path.is_symlink():
            fail(f"distribution: symbolic links are prohibited: {relative}")
        if not path.is_file():
            fail(f"distribution: tracked path is not a regular file: {relative}")

    expected = set(distribution_files)
    overlap = [
        path
        for path in distribution_files
        if any(descendant(path, entry) for entry in forbidden)
    ]
    if overlap:
        fail(
            "distribution manifest: distribution and forbidden paths overlap: "
            f"{overlap!r}"
        )

    missing = sorted(expected - set(actual))
    undeclared = sorted(set(actual) - expected)
    if missing:
        fail(f"distribution: declared files are missing: {missing!r}")
    if undeclared:
        fail(f"distribution: undeclared files are present: {undeclared!r}")

    present_forbidden = sorted(
        path
        for path in actual
        if any(descendant(path, entry) for entry in forbidden)
    )
    if present_forbidden:
        fail(
            "distribution: maintainer-only paths are present: "
            f"{present_forbidden!r}"
        )

    actual_top_level = sorted({path.split("/", 1)[0] for path in actual})
    if actual_top_level != required_top_level:
        fail(
            "distribution: top-level inventory differs; "
            f"expected={required_top_level!r}, actual={actual_top_level!r}"
        )

    for relative in distribution_files:
        path = root / source_root / relative
        mode = actual[relative]
        if mode == "120000" or path.is_symlink():
            fail(f"distribution file may not be a symbolic link: {relative}")
        if not path.is_file():
            fail(f"distribution path is not a regular file: {relative}")

    print(f"Skill template distribution is valid. {len(actual)} canonical files.")
    return True


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print(f"usage: python {Path(__file__).name} [SOURCE_ROOT]", file=sys.stderr)
        return 2
    try:
        validate(argv[0] if argv else ".")
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"distribution: cannot inspect required file: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
