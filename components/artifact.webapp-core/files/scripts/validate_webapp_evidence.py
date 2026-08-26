#!/usr/bin/env python3
"""Validate Webapp-specific implementation-evidence coverage and proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .webapp_evidence_targets import (
        BROWSER_LEVEL_PROOF_KINDS,
        DOMAIN_IDS,
        BROWSER_SENSITIVE_CONTRACT_ITEMS,
        allowed_targets,
        expected_targets,
        requires_browser_level_proof,
        target_key,
    )
else:
    from webapp_evidence_targets import (
        BROWSER_LEVEL_PROOF_KINDS,
        DOMAIN_IDS,
        BROWSER_SENSITIVE_CONTRACT_ITEMS,
        allowed_targets,
        expected_targets,
        requires_browser_level_proof,
        target_key,
    )


def load(root: Path, relative: str) -> object:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def actual_targets(evidence: object) -> list[tuple[Any, ...]]:
    if not isinstance(evidence, dict):
        raise TypeError("implementation evidence root must be a JSON object")

    records = evidence.get("records")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")

    actual: list[tuple[Any, ...]] = []
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



def browser_level_proof_errors(evidence: dict[str, Any]) -> list[str]:
    records = evidence.get("records")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")

    errors: list[str] = []
    allowed_kinds = ", ".join(sorted(BROWSER_LEVEL_PROOF_KINDS))
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"implementation evidence record {index} must be a JSON object")
        target = record.get("target")
        if not requires_browser_level_proof(target):
            continue
        if not isinstance(target, dict):
            raise TypeError(
                f"implementation evidence record {index} target must be a JSON object"
            )
        key = target_key(target)
        for field, label in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            proofs = record.get(field)
            if not isinstance(proofs, list):
                raise TypeError(
                    f"implementation evidence record {index} {field} must be a JSON array"
                )
            kinds = {
                proof.get("kind")
                for proof in proofs
                if isinstance(proof, dict) and isinstance(proof.get("kind"), str)
            }
            if kinds.isdisjoint(BROWSER_LEVEL_PROOF_KINDS):
                errors.append(
                    f"browser-sensitive Webapp target {key} requires at least one "
                    f"{label} browser-level proof kind ({allowed_kinds})"
                )
    return errors


def browser_level_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")
    if requirements is None:
        return []
    if not isinstance(requirements, list):
        raise TypeError("implementation evidence requirements must be a JSON array")

    targets_by_record_id: dict[str, object] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"implementation evidence record {index} must be a JSON object")
        record_id = record.get("id")
        if isinstance(record_id, str):
            targets_by_record_id[record_id] = record.get("target")

    allowed_kinds = ", ".join(sorted(BROWSER_LEVEL_PROOF_KINDS))
    errors: list[str] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise TypeError(f"implementation evidence requirement {index} must be a JSON object")
        record_ids = requirement.get("recordIds")
        if not isinstance(record_ids, list):
            raise TypeError(
                f"implementation evidence requirement {index} recordIds must be a JSON array"
            )
        if not any(
            isinstance(record_id, str)
            and requires_browser_level_proof(targets_by_record_id.get(record_id))
            for record_id in record_ids
        ):
            continue
        kinds = requirement.get("requiredPositiveProofKinds")
        declared = {
            kind for kind in kinds if isinstance(kind, str)
        } if isinstance(kinds, list) else set()
        if declared.isdisjoint(BROWSER_LEVEL_PROOF_KINDS):
            requirement_id = requirement.get("id", f"index-{index}")
            errors.append(
                f"requirement {requirement_id!r} references a browser-sensitive Webapp "
                f"target and must declare at least one browser-level requiredPositiveProofKinds "
                f"value ({allowed_kinds})"
            )
    return errors


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
        mode = evidence.get("mode")
        if mode == "template":
            print("Webapp evidence coverage: template mode OK")
            return 0
        if mode == "planning":
            print("Webapp evidence coverage: planning mode; product target coverage pending")
            return 0
        if mode != "product":
            raise ValueError(f"unsupported implementation-evidence mode: {mode!r}")
        actual = actual_targets(evidence)
        strength_errors = browser_level_proof_errors(evidence)
        strength_errors.extend(browser_level_requirement_errors(evidence))
    except (AttributeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot load Webapp implementation evidence: {exc}", file=sys.stderr)
        return 1

    errors = []
    seen: set[tuple[Any, ...]] = set()
    duplicates: set[tuple[Any, ...]] = set()
    for item in actual:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    for duplicate in sorted(duplicates, key=str):
        errors.append(f"duplicate Webapp implementation-evidence target: {duplicate}")

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
        if len(extra) >= 2 and extra[1] in DOMAIN_IDS:
            errors.append(f"unknown Webapp implementation-evidence target: {extra}")
    errors.extend(strength_errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Webapp evidence coverage and proof strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
