#!/usr/bin/env python3
"""Render a deterministic non-canonical Webapp implementation-evidence worklist."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .webapp_evidence_targets import expected_targets, record_id
else:
    from webapp_evidence_targets import expected_targets, record_id


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Webapp repository root; defaults to the current directory",
    )
    args = parser.parse_args()
    try:
        worklist = render_worklist(Path(args.root))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Webapp evidence scaffold failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(worklist, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
