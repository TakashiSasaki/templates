#!/usr/bin/env python3
"""Render a deterministic candidate publication lock without mutating the lock.

The command is used by a trusted controller after qualification. Provider
revisions are data here; no provider checkout or provider executable is run.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.resolve_publication_sources import (
    SourceLockError,
    parse_overrides,
    render_source_lock,
    resolve_candidate_sources,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=Path("publication-sources.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--override", action="append", default=[], metavar="NAME=SHA")
    parser.add_argument("--candidate-provider", action="append", default=[])
    args = parser.parse_args()
    try:
        overrides = parse_overrides(args.override)
        resolved = resolve_candidate_sources(
            args.lock,
            overrides,
            required_new_providers=tuple(args.candidate_provider),
        )
        if args.output.is_symlink() or args.output.exists():
            raise SourceLockError("candidate output already exists or is a symbolic link")
        args.output.write_bytes(render_source_lock(resolved))
    except (OSError, SourceLockError, ValueError) as exc:
        print(f"candidate source-lock rendering failed: {exc}", file=sys.stderr)
        return 1
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
