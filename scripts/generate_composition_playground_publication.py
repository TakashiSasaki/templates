#!/usr/bin/env python3
"""Generate and validate immutable gzip Composition Playground publication assets."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Sequence

from composer_core_impl import CompositionError, load_json_bytes
from generate_composition_playground import build_projection, render_projection
from generate_composition_playground_intent import build_intent_projection

BASE_NAME = "composition-playground-v1.json.gz"
INTENT_NAME = "composition-playground-intent-v1.json.gz"


def compress_payload(data: bytes) -> bytes:
    compressed = bytearray(gzip.compress(data, compresslevel=9, mtime=0))
    if len(compressed) < 10:
        raise CompositionError("PLAYGROUND_GZIP_FAILED", "gzip output is unexpectedly short")
    compressed[9] = 255
    return bytes(compressed)


def semantic_revision_from_gzip(path: Path) -> str:
    try:
        raw = gzip.decompress(path.read_bytes())
        projection = load_json_bytes(raw, label=str(path))
        revision = projection["source"]["revision"]
    except (OSError, EOFError, gzip.BadGzipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", f"cannot read Playground semantic source revision from {path}: {exc}") from exc
    if not isinstance(revision, str) or len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "published Playground semantic source revision is not an exact lowercase SHA")
    return revision


def publication_payloads(*, semantic_revision: str | None = None) -> dict[str, bytes]:
    base = render_projection(build_projection(source_revision=semantic_revision))
    intent = (json.dumps(build_intent_projection(source_revision=semantic_revision), indent=2, sort_keys=False) + "\n").encode()
    return {BASE_NAME: compress_payload(base), INTENT_NAME: compress_payload(intent)}


def check_directory(directory: Path, *, semantic_revision: str | None = None) -> str:
    base_path = directory / BASE_NAME
    intent_path = directory / INTENT_NAME
    revision = semantic_revision or semantic_revision_from_gzip(base_path)
    if semantic_revision_from_gzip(intent_path) != revision:
        raise CompositionError("INVALID_PLAYGROUND_PUBLICATION", "resolution and intent projections have different semantic source revisions")
    expected = publication_payloads(semantic_revision=revision)
    for name, payload in expected.items():
        path = directory / name
        try:
            current = path.read_bytes()
        except OSError as exc:
            raise CompositionError("READ_FAILED", f"cannot read publication asset {path}: {exc}") from exc
        if current != payload:
            raise CompositionError("STALE_PLAYGROUND_PUBLICATION", f"{path} is not the deterministic current Playground publication asset")
    return revision


def write_directory(directory: Path, *, semantic_revision: str | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in publication_payloads(semantic_revision=semantic_revision).items():
        (directory / name).write_bytes(payload)


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
            write_directory(args.output_dir, semantic_revision=args.semantic_revision)
            print(args.output_dir)
        return 0
    except (CompositionError, json.JSONDecodeError) as exc:
        if isinstance(exc, CompositionError):
            print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        else:
            print(f"ERROR [INVALID_PLAYGROUND_PUBLICATION]: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
