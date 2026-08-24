#!/usr/bin/env python3
"""Validate Webapp-specific implementation-evidence target coverage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .webapp_evidence_targets import allowed_targets, expected_targets, target_key
else:
    from webapp_evidence_targets import allowed_targets, expected_targets, target_key


def load(root: Path, relative: str) -> object:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def actual_targets(evidence: object) -> list[str]:
    if not isinstance(evidence, dict):
        raise TypeError("implementation evidence root must be a JSON object")

    records = evidence.get("records")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")

    actual: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"implementation evidence record {index} must be a JSON object")
        target = record.get("target")
        if not isinstance(target, dict):
            raise TypeError(
                f"implementation evidence record {index} target must be a JSON object"
            )
        actual.append(target_key(target))
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Webapp repository root; defaults to the current directory",
    )
    args = parser.parse_args()
    root = Path(args.root)

    try:
        evidence = load(root, "contracts/implementation-evidence.json")
        if not isinstance(evidence, dict):
            raise TypeError("implementation evidence root must be a JSON object")
        if evidence.get("mode") == "template":
            print("Webapp evidence coverage: template mode OK")
            return 0
        actual = actual_targets(evidence)
    except (AttributeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot load Webapp implementation evidence: {exc}", file=sys.stderr)
        return 1

    errors = []
    if len(actual) != len(set(actual)):
        errors.append("duplicate Webapp implementation-evidence target")

    try:
        expected = {target_key(target) for target in expected_targets(root)}
        allowed = {target_key(target) for target in allowed_targets(root)}
    except (AttributeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot derive Webapp implementation-evidence targets: {exc}", file=sys.stderr)
        return 1

    actual_set = set(actual)
    for missing in sorted(expected - actual_set, key=str):
        errors.append(f"missing Webapp implementation-evidence target: {missing}")
    for extra in sorted(actual_set - allowed, key=str):
        errors.append(f"unknown Webapp implementation-evidence target: {extra}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Webapp evidence coverage: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
