#!/usr/bin/env python3
"""Render a deterministic non-canonical Webapp implementation-evidence worklist."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .webapp_evidence_targets import expected_targets, record_id
else:
    from webapp_evidence_targets import expected_targets, record_id


CANONICAL_EVIDENCE = Path("contracts/implementation-evidence.json")


def record_skeleton(target: dict[str, Any]) -> dict[str, Any]:
    identifier = record_id(target)
    return {
        "id": identifier,
        "target": target,
        "implementationBoundary": {
            "status": "required",
            "description": "TODO: identify the product implementation boundary for this target.",
        },
        "positiveEvidence": [
            {
                "id": f"{identifier}-positive",
                "status": "required",
                "description": "TODO: identify positive evidence for this target.",
            }
        ],
        "negativeEvidence": [
            {
                "id": f"{identifier}-negative",
                "status": "required",
                "description": "TODO: identify negative evidence for this target.",
            }
        ],
        "releaseGateIds": [],
    }


def render_worklist(root: Path) -> dict[str, Any]:
    targets = expected_targets(root)
    records = [record_skeleton(target) for target in targets]
    identifiers = [record["id"] for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Webapp evidence worklist produces duplicate record ids")
    return {
        "format": "webapp-implementation-evidence-worklist",
        "formatVersion": 1,
        "recordCount": len(records),
        "records": records,
    }


def resolve_output(root: Path, value: str) -> Path:
    requested = Path(value)
    candidate = requested if requested.is_absolute() else root / requested
    candidate = candidate.absolute()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "--output must stay within the Webapp repository root: "
            f"{resolved} is outside {root}"
        ) from exc

    canonical = (root / CANONICAL_EVIDENCE).resolve(strict=False)
    if resolved == canonical:
        raise ValueError(
            "--output refuses the canonical implementation-evidence document; "
            "write the non-canonical worklist to a separate consumer-owned file"
        )
    return candidate


def write_worklist(root: Path, output: str, worklist: dict[str, Any]) -> None:
    destination = resolve_output(root, output)
    parent = destination.parent
    if not parent.exists():
        raise ValueError(f"--output parent does not exist: {parent}")
    if not parent.is_dir():
        raise ValueError(f"--output parent is not a directory: {parent}")
    if os.path.lexists(destination):
        raise FileExistsError(f"--output path already exists: {destination}")

    payload = json.dumps(worklist, indent=2, ensure_ascii=False) + "\n"
    created = False
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Webapp repository root; defaults to the current directory",
    )
    parser.add_argument(
        "--output",
        help=(
            "write the worklist to a new consumer-owned file relative to the Webapp "
            "repository root instead of standard output; existing paths and the canonical "
            "implementation-evidence document are refused"
        ),
    )
    args = parser.parse_args()
    try:
        root = Path(args.root).resolve()
        worklist = render_worklist(root)
        if args.output is None:
            print(json.dumps(worklist, indent=2, ensure_ascii=False))
        else:
            write_worklist(root, args.output, worklist)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Webapp evidence scaffold failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
