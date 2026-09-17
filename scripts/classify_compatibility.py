#!/usr/bin/env python3
"""CLI for the Integration-owned structured compatibility classifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.compatibility import classify_preflight, classify_qualification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("preflight", "qualification"), default="preflight")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = classify_preflight(payload) if args.stage == "preflight" else classify_qualification(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {
            "schema_version": 1,
            "boundary": None,
            "stage": args.stage,
            "classification": "INVALID_INPUT",
            "reason_codes": ["INVALID_REPORT_INPUT"],
            "affected_authorities": ["integration"],
            "inputs": {},
            "trusted": {"policy_revision": None, "controller_revision": None},
            "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
            "checks": {"required": [], "results": {}, "not_run": []},
            "evidence_refs": [str(exc)],
            "allowed_mutations": [],
            "next_action": "stop",
            "idempotency_key": "0" * 64,
        }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["classification"])
    return 0 if report["classification"] in {"COMPATIBLE_PENDING_QUALIFICATION", "AUTO_PROCESSABLE", "NO_CHANGE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
