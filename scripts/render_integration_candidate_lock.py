#!/usr/bin/env python3
"""Render the only Site-owned Integration selection mutation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def render(args: argparse.Namespace) -> dict:
    if not SHA.fullmatch(args.revision) or not DIGEST.fullmatch(args.bundle_identity) or not DIGEST.fullmatch(args.content_digest):
        raise ValueError("candidate identities must be full lowercase SHA/SHA-256 values")
    if args.bundle_schema not in {3, 4}:
        raise ValueError("unsupported candidate Bundle schema")
    value = {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "revision": args.revision,
        "bundle_schema": args.bundle_schema,
        "bundle_identity": args.bundle_identity,
        "content_digest": args.content_digest,
    }
    if args.output.is_symlink() or args.output.exists():
        raise ValueError("candidate lock output already exists or is a symbolic link")
    args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--bundle-schema", type=int, required=True)
    parser.add_argument("--bundle-identity", required=True)
    parser.add_argument("--content-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(render(args), sort_keys=True))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
