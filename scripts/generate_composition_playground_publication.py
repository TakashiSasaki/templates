#!/usr/bin/env python3
"""Package and validate the immutable Composition Playground publication asset."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Sequence

from composer_core_impl import CompositionError, load_json_bytes
from generate_composition_playground import build_projection, render_projection


def compress_projection(data: bytes) -> bytes:
    """Return a deterministic gzip transport for canonical projection JSON."""
    compressed = bytearray(gzip.compress(data, compresslevel=9, mtime=0))
    if len(compressed) < 10:
        raise CompositionError("PLAYGROUND_GZIP_FAILED", "gzip output is unexpectedly short")
    # Normalize the RFC 1952 OS byte so the publication bytes are platform-neutral.
    compressed[9] = 255
    return bytes(compressed)


def semantic_revision_from_gzip(path: Path) -> str:
    """Return the semantic Composition revision embedded in the projection.

    This is intentionally distinct from the provider/publication revision that
    carries the gzip asset. The canonical generator verifies that the semantic
    revision is an ancestor of the provider checkout and that Playground semantic
    paths have not changed between them.
    """
    try:
        compressed = path.read_bytes()
        raw = gzip.decompress(compressed)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            f"cannot read gzip Playground projection {path}: {exc}",
        ) from exc
    projection = load_json_bytes(raw, label=str(path))
    try:
        revision = projection["source"]["revision"]
    except (KeyError, TypeError) as exc:
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            "published Playground projection has no semantic source revision",
        ) from exc
    if not isinstance(revision, str):
        raise CompositionError(
            "INVALID_PLAYGROUND_PUBLICATION",
            "published Playground semantic source revision is not a string",
        )
    return revision


def publication_bytes(*, semantic_revision: str | None = None) -> bytes:
    """Render transport bytes after authoritative semantic/provider validation."""
    return compress_projection(
        render_projection(build_projection(source_revision=semantic_revision))
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--output", type=Path)
    output.add_argument("--check", type=Path)
    parser.add_argument(
        "--semantic-revision",
        help="bind output to this exact semantically equivalent Composition revision",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check is not None:
            semantic_revision = args.semantic_revision or semantic_revision_from_gzip(args.check)
            expected = publication_bytes(semantic_revision=semantic_revision)
            try:
                current = args.check.read_bytes()
            except OSError as exc:
                raise CompositionError(
                    "READ_FAILED", f"cannot read publication asset {args.check}: {exc}"
                ) from exc
            if current != expected:
                raise CompositionError(
                    "STALE_PLAYGROUND_PUBLICATION",
                    f"{args.check} is not the deterministic current Playground publication asset",
                )
            print(
                "Composition Playground publication is current: "
                f"{args.check} (semantic source {semantic_revision})"
            )
            return 0

        semantic_revision = args.semantic_revision
        payload = publication_bytes(semantic_revision=semantic_revision)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        print(args.output)
        return 0
    except (CompositionError, json.JSONDecodeError) as exc:
        if isinstance(exc, CompositionError):
            print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        else:
            print(f"ERROR [INVALID_PLAYGROUND_PUBLICATION]: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
