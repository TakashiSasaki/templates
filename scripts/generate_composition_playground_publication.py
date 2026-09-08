#!/usr/bin/env python3
"""Generate and validate deterministic Composition Playground publication assets."""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from composer_core_impl import CompositionError, load_json_bytes
from generate_composition_playground import SEMANTIC_PATHS, build_projection, render_projection
from generate_composition_playground_intent import build_intent_projection

ROOT = Path(__file__).resolve().parents[1]
BASE_NAME = "composition-playground-v1.json.gz"
INTENT_NAME = "composition-playground-intent-v1.json.gz"
MANIFEST_NAME = "composition-playground-publication.json"
_GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40}$")


def compress_payload(data: bytes) -> bytes:
    compressed = bytearray(gzip.compress(data, compresslevel=9, mtime=0))
    if len(compressed) < 10:
        raise CompositionError("PLAYGROUND_GZIP_FAILED", "gzip output is unexpectedly short")
    compressed[9] = 255
    return bytes(compressed)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise CompositionError("GIT_UNAVAILABLE", f"cannot execute git: {exc}") from exc


def verify_semantic_snapshot(semantic_objects: Mapping[str, str]) -> None:
    """Verify semantic inputs from the current checkout without Git history.

    Publication manifests pin the Git object identity of every path that defines
    Playground semantics.  A shallow exact checkout therefore needs only its
    current HEAD tree; it does not need the historical semantic commit object or
    an ancestry walk.  The working tree must also be clean across those paths so
    generation cannot silently consume bytes that differ from the pinned tree.
    """
    if set(semantic_objects) != set(SEMANTIC_PATHS):
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            "Playground publication semantic object inventory is invalid",
        )

    status = _run_git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *SEMANTIC_PATHS,
    )
    if status.returncode != 0:
        raise CompositionError(
            "GIT_FAILED",
            f"cannot inspect Playground semantic working tree: {status.stderr.strip()}",
        )
    if status.stdout.strip():
        raise CompositionError(
            "STALE_PLAYGROUND_SOURCE",
            "Composition semantic inputs differ from the checked-out HEAD tree",
        )

    for path in SEMANTIC_PATHS:
        expected = semantic_objects[path]
        if not isinstance(expected, str) or not _GIT_OBJECT_RE.fullmatch(expected):
            raise CompositionError(
                "INVALID_PLAYGROUND_PUBLICATION",
                f"invalid semantic Git object identity for {path}",
            )
        current = _run_git("rev-parse", f"HEAD:{path}")
        if current.returncode != 0:
            raise CompositionError(
                "GIT_FAILED",
                f"cannot resolve Playground semantic object {path}: {current.stderr.strip()}",
            )
        if current.stdout.strip() != expected:
            raise CompositionError(
                "STALE_PLAYGROUND_SOURCE",
                f"Composition semantic input {path} does not match the publication snapshot",
            )


def read_publication_manifest(directory: Path) -> dict[str, object]:
    path = directory / MANIFEST_NAME
    try:
        value = load_json_bytes(path.read_bytes(), label=str(path))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            f"cannot read Playground publication manifest {path}: {exc}",
        ) from exc
    expected_keys = {
        "schema_version",
        "projection_id",
        "intent_projection_id",
        "semantic_revision",
        "semantic_objects",
        "assets",
    }
    if set(value) != expected_keys or value.get("schema_version") != 2:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication manifest shape is invalid")
    if value.get("projection_id") != "composition-playground-v1" or value.get("intent_projection_id") != "composition-playground-intent-v1":
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication manifest projection identity is invalid")
    if value.get("assets") != [BASE_NAME, INTENT_NAME]:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication manifest asset inventory is invalid")
    revision = value.get("semantic_revision")
    if not isinstance(revision, str) or not _GIT_OBJECT_RE.fullmatch(revision):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication semantic revision is not an exact lowercase SHA")
    semantic_objects = value.get("semantic_objects")
    if not isinstance(semantic_objects, dict) or set(semantic_objects) != set(SEMANTIC_PATHS):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication semantic object inventory is invalid")
    if any(not isinstance(item, str) or not _GIT_OBJECT_RE.fullmatch(item) for item in semantic_objects.values()):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "Playground publication semantic object identity is invalid")
    return value


def semantic_revision_from_manifest(directory: Path) -> str:
    revision = read_publication_manifest(directory)["semantic_revision"]
    assert isinstance(revision, str)
    return revision


def semantic_objects_from_manifest(directory: Path) -> dict[str, str]:
    value = read_publication_manifest(directory)["semantic_objects"]
    assert isinstance(value, dict)
    return {str(path): str(object_id) for path, object_id in value.items()}


def semantic_revision_from_gzip(path: Path) -> str:
    try:
        raw = gzip.decompress(path.read_bytes())
        projection = load_json_bytes(raw, label=str(path))
        revision = projection["source"]["revision"]
    except (OSError, EOFError, gzip.BadGzipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", f"cannot read Playground semantic source revision from {path}: {exc}") from exc
    if not isinstance(revision, str) or not _GIT_OBJECT_RE.fullmatch(revision):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "published Playground semantic source revision is not an exact lowercase SHA")
    return revision


def _bind_semantic_revision(projection: dict[str, object], semantic_revision: str) -> dict[str, object]:
    source = projection.get("source")
    if not isinstance(source, dict):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "generated projection has no source object")
    source["revision"] = semantic_revision
    return projection


def publication_payloads(*, semantic_revision: str, semantic_objects: Mapping[str, str]) -> dict[str, bytes]:
    verify_semantic_snapshot(semantic_objects)

    # Generate from the exact current checkout so the canonical generators do
    # not need historical objects.  The snapshot check above proves that every
    # semantic input is byte-for-byte the object pinned for semantic_revision;
    # rebinding the provenance label therefore preserves the canonical semantic
    # source while remaining valid in fetch-depth:1 consumer checkouts.
    base_projection = _bind_semantic_revision(build_projection(), semantic_revision)
    intent_projection = _bind_semantic_revision(build_intent_projection(), semantic_revision)
    base = render_projection(base_projection)
    intent = (json.dumps(intent_projection, indent=2, sort_keys=False) + "\n").encode()
    return {BASE_NAME: compress_payload(base), INTENT_NAME: compress_payload(intent)}


def resolve_revision(directory: Path, semantic_revision: str | None) -> str:
    manifest_revision = semantic_revision_from_manifest(directory)
    if semantic_revision is not None and semantic_revision != manifest_revision:
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            f"explicit semantic revision {semantic_revision} does not match publication manifest {manifest_revision}",
        )
    return manifest_revision


def check_directory(directory: Path, *, semantic_revision: str | None = None) -> str:
    revision = resolve_revision(directory, semantic_revision)
    semantic_objects = semantic_objects_from_manifest(directory)
    base_path = directory / BASE_NAME
    intent_path = directory / INTENT_NAME
    if semantic_revision_from_gzip(base_path) != revision or semantic_revision_from_gzip(intent_path) != revision:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "published projections do not match manifest semantic revision")
    expected = publication_payloads(semantic_revision=revision, semantic_objects=semantic_objects)
    for name, payload in expected.items():
        path = directory / name
        try:
            current = path.read_bytes()
        except OSError as exc:
            raise CompositionError("READ_FAILED", f"cannot read publication asset {path}: {exc}") from exc
        if current != payload:
            raise CompositionError("STALE_PLAYGROUND_PUBLICATION", f"{path} is not the deterministic current Playground publication asset")
    return revision


def write_directory(directory: Path, *, semantic_revision: str | None = None) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    revision = resolve_revision(directory, semantic_revision)
    semantic_objects = semantic_objects_from_manifest(directory)
    for name, payload in publication_payloads(
        semantic_revision=revision,
        semantic_objects=semantic_objects,
    ).items():
        (directory / name).write_bytes(payload)
    return revision


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output-dir", type=Path)
    group.add_argument("--check-dir", type=Path)
    parser.add_argument("--semantic-revision")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_dir is not None:
            revision = check_directory(args.check_dir, semantic_revision=args.semantic_revision)
            print(f"Composition Playground publication is current: {args.check_dir} (semantic source {revision})")
        else:
            revision = write_directory(args.output_dir, semantic_revision=args.semantic_revision)
            print(f"{args.output_dir} (semantic source {revision})")
        return 0
    except (CompositionError, json.JSONDecodeError) as exc:
        if isinstance(exc, CompositionError):
            print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        else:
            print(f"ERROR [INVALID_PLAYGROUND_PUBLICATION]: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
