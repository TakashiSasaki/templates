#!/usr/bin/env python3
"""Resolve full-SHA publication locks with explicit reviewed overrides."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, TextIO

EXPECTED_REPOSITORY = "TakashiSasaki/templates"
PUBLICATION_NAMES = ("composition", "policy")
FULL_COMMIT_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
NAME_PATTERN = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class SourceLockError(RuntimeError):
    """Raised when the publication source lock or an override is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("publication-sources.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="NAME=REF",
    )
    return parser.parse_args()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SourceLockError(
            f"unable to read publication source lock {path}: {exc}"
        ) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceLockError(
            f"publication source lock must be valid UTF-8: {path}"
        ) from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SourceLockError(
                    "publication source lock contains duplicate object member: "
                    f"{key}"
                )
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise SourceLockError(
            f"unable to parse publication source lock {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SourceLockError("publication source lock must be a JSON object")
    return data


def parse_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for index, value in enumerate(values):
        if "=" not in value:
            raise SourceLockError(
                f"override {index} must use NAME=REF syntax: {value!r}"
            )
        name, ref = value.split("=", 1)
        if not NAME_PATTERN.fullmatch(name):
            raise SourceLockError(
                f"override {index} name must be lowercase kebab-case"
            )
        if name not in PUBLICATION_NAMES:
            raise SourceLockError(f"override references unknown publication: {name}")
        if not ref:
            raise SourceLockError(f"override for {name} must not be empty")
        if name in overrides:
            raise SourceLockError(f"duplicate override: {name}")
        overrides[name] = ref
    return overrides


def validate_locked_revisions(revisions: dict[str, str]) -> dict[str, str]:
    if set(revisions) != set(PUBLICATION_NAMES):
        raise SourceLockError(
            "publication revisions must define exactly: "
            + ", ".join(PUBLICATION_NAMES)
        )
    validated: dict[str, str] = {}
    for name in PUBLICATION_NAMES:
        revision = revisions[name]
        if not isinstance(revision, str) or not FULL_COMMIT_PATTERN.fullmatch(revision):
            raise SourceLockError(
                f"{name} locked revision must be a full lowercase commit SHA"
            )
        validated[name] = revision
    return validated


def render_source_lock(revisions: dict[str, str]) -> bytes:
    """Render the canonical schema-v1 publication source lock."""
    validated = validate_locked_revisions(revisions)
    value = {
        "schema_version": 1,
        "repository": EXPECTED_REPOSITORY,
        "publications": {
            name: {"revision": validated[name]} for name in PUBLICATION_NAMES
        },
    }
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def resolve_sources(path: Path, overrides: dict[str, str]) -> dict[str, str]:
    data = read_json_object(path)
    expected = {"schema_version", "repository", "publications"}
    unknown = set(data) - expected
    missing = expected - set(data)
    if unknown:
        raise SourceLockError(
            "publication source lock contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    if missing:
        raise SourceLockError(
            "publication source lock is missing required fields: "
            + ", ".join(sorted(missing))
        )
    schema_version = data["schema_version"]
    if type(schema_version) is not int or schema_version != 1:
        raise SourceLockError("schema_version must be the integer 1")
    if data["repository"] != EXPECTED_REPOSITORY:
        raise SourceLockError(
            f"repository must be {EXPECTED_REPOSITORY!r}"
        )

    publications = data["publications"]
    if not isinstance(publications, dict):
        raise SourceLockError("publications must be an object")
    if set(publications) != set(PUBLICATION_NAMES):
        raise SourceLockError(
            "publications must define exactly: "
            + ", ".join(PUBLICATION_NAMES)
        )

    locked: dict[str, str] = {}
    for name in PUBLICATION_NAMES:
        entry = publications[name]
        if not isinstance(entry, dict) or set(entry) != {"revision"}:
            raise SourceLockError(
                f"{name} publication entry must contain only revision"
            )
        locked[name] = entry["revision"]
    validated = validate_locked_revisions(locked)
    return {
        name: overrides.get(name, validated[name]) for name in PUBLICATION_NAMES
    }


def write_outputs(output: TextIO, resolved: dict[str, str]) -> None:
    for name in PUBLICATION_NAMES:
        output.write(f"{name}={resolved[name]}\n")


def main() -> int:
    args = parse_args()
    try:
        resolved = resolve_sources(args.lock, parse_overrides(args.override))
        if args.output is None:
            write_outputs(sys.stdout, resolved)
        else:
            with args.output.open("a", encoding="utf-8") as output:
                write_outputs(output, resolved)
    except (OSError, SourceLockError) as exc:
        print(f"publication source resolution failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
