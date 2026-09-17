#!/usr/bin/env python3
"""Validate exact revision relationships in Composition Playground artifacts."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
BASE_PROJECTION_ID = "composition-playground-v1"
INTENT_PROJECTION_ID = "composition-playground-intent-v1"
BASE_ASSET = "composition-playground-v1.json.gz"
INTENT_ASSET = "composition-playground-intent-v1.json.gz"
MANIFEST = "composition-playground-publication.json"


class ProvenanceError(RuntimeError):
    """Raised when a Playground artifact is malformed or stale."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"JSON artifact must contain an object: {path}")
    return value


def _revision(value: Any, label: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise ProvenanceError(f"{label} must be an exact lowercase commit SHA")
    return value


def _projection_revision(value: dict[str, Any], label: str) -> str:
    source = value.get("source")
    if not isinstance(source, dict):
        raise ProvenanceError(f"{label} has no source object")
    return _revision(source.get("revision"), f"{label} source revision")


def validate_projections(paths: Sequence[Path], *, expected_head: str | None = None) -> str:
    if len(paths) != 2:
        raise ProvenanceError("exactly two Playground projections are required")
    values = [_json(path) for path in paths]
    expected_ids = (BASE_PROJECTION_ID, INTENT_PROJECTION_ID)
    for value, path, expected_id in zip(values, paths, expected_ids):
        if value.get("projection_id") != expected_id:
            raise ProvenanceError(
                f"{path} must declare projection_id {expected_id!r}"
            )
    revisions = [_projection_revision(value, str(path)) for value, path in zip(values, paths)]
    if revisions[0] != revisions[1]:
        raise ProvenanceError("base and intent projection source revisions differ")
    if expected_head is not None and revisions[0] != _revision(expected_head, "expected head"):
        raise ProvenanceError(
            f"projection source revision {revisions[0]} does not match expected head {expected_head}"
        )
    return revisions[0]


def _compressed_projection(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, EOFError, gzip.BadGzipFile, UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"cannot read compressed projection {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"compressed projection must contain an object: {path}")
    return value


def validate_publication(directory: Path, *, expected_revision: str | None = None) -> str:
    manifest = _json(directory / MANIFEST)
    if manifest.get("projection_id") != BASE_PROJECTION_ID:
        raise ProvenanceError("publication manifest has the wrong base projection identity")
    if manifest.get("intent_projection_id") != INTENT_PROJECTION_ID:
        raise ProvenanceError("publication manifest has the wrong intent projection identity")
    revision = _revision(manifest.get("semantic_revision"), "publication semantic revision")
    if manifest.get("assets") != [BASE_ASSET, INTENT_ASSET]:
        raise ProvenanceError("publication manifest asset inventory is not canonical")
    if expected_revision is not None and revision != _revision(
        expected_revision, "expected semantic revision"
    ):
        raise ProvenanceError(
            f"publication semantic revision {revision} does not match expected {expected_revision}"
        )
    for name, projection_id in (
        (BASE_ASSET, BASE_PROJECTION_ID),
        (INTENT_ASSET, INTENT_PROJECTION_ID),
    ):
        projection = _compressed_projection(directory / name)
        if projection.get("projection_id") != projection_id:
            raise ProvenanceError(f"{name} has the wrong projection identity")
        if _projection_revision(projection, name) != revision:
            raise ProvenanceError(f"{name} is not bound to the publication semantic revision")
    catalog = _json(directory.parent / "docs" / "publication-catalog.json")
    assets = catalog.get("assets")
    expected_assets = [
        {
            "source": f"generated/{BASE_ASSET}",
            "destination": f"playground/{BASE_ASSET}",
            "optional": False,
        },
        {
            "source": f"generated/{INTENT_ASSET}",
            "destination": f"playground/{INTENT_ASSET}",
            "optional": False,
        },
    ]
    if not isinstance(assets, list) or [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("destination", "")).startswith("playground/composition-playground")
    ] != expected_assets:
        raise ProvenanceError("publication catalog Playground assets are not canonical")
    return revision


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--projection", action="append", type=Path)
    group.add_argument("--publication-dir", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-semantic-revision")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.projection is not None:
            if args.expected_semantic_revision is not None:
                raise ProvenanceError(
                    "--expected-semantic-revision is only valid for --publication-dir"
                )
            revision = validate_projections(args.projection, expected_head=args.expected_head)
        else:
            if args.expected_head is not None:
                raise ProvenanceError("--expected-head is only valid for --projection")
            revision = validate_publication(
                args.publication_dir,
                expected_revision=args.expected_semantic_revision,
            )
    except ProvenanceError as exc:
        print(f"ERROR [PLAYGROUND_PROVENANCE]: {exc}", file=sys.stderr)
        return 1
    print(f"Composition Playground provenance: OK (revision {revision})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
