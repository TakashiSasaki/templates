#!/usr/bin/env python3
"""Validate Webapp-specific implementation-evidence target coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from webapp_evidence_targets import expected_targets, target_key

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    evidence = load("contracts/implementation-evidence.json")
    if evidence.get("mode") == "template":
        print("Webapp evidence coverage: template mode OK")
        return 0

    actual = [target_key(record["target"]) for record in evidence.get("records", [])]
    errors = []
    if len(actual) != len(set(actual)):
        errors.append("duplicate Webapp implementation-evidence target")

    try:
        expected = {target_key(target) for target in expected_targets(ROOT)}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot derive Webapp implementation-evidence targets: {exc}", file=sys.stderr)
        return 1

    actual_set = set(actual)
    for missing in sorted(expected - actual_set, key=str):
        errors.append(f"missing Webapp implementation-evidence target: {missing}")
    for extra in sorted(actual_set - expected, key=str):
        errors.append(f"unknown Webapp implementation-evidence target: {extra}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Webapp evidence coverage: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
