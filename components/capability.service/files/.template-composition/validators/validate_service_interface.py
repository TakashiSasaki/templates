#!/usr/bin/env python3
"""Validate selected service contracts and executable implementation evidence."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SERVICE_CONTRACT = Path("contracts/service-interface.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
EXECUTABLE_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def target_key(target: object) -> tuple[object, ...]:
    if not isinstance(target, dict):
        return (None, None, None, None)
    return (target.get("kind"), target.get("contractId"), target.get("itemKind"), target.get("itemId"))


def service_target(operation_id: str) -> tuple[str, str, str, str]:
    return ("contract-item", "service_interface", "operation", operation_id)


def executable_proof_present(record: dict[str, Any], field: str) -> bool:
    proofs = record.get(field)
    return isinstance(proofs, list) and any(
        isinstance(proof, dict)
        and proof.get("status") == "verified"
        and proof.get("kind") in EXECUTABLE_PROOF_KINDS
        for proof in proofs
    )


def planning_requirement_errors(contract: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    operations = contract.get("operations")
    requirements = evidence.get("requirements")
    if not isinstance(operations, list):
        return ["planning service contract operations must be an array"]
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]

    errors: list[str] = []
    planned_ids = [op.get("id") for op in operations if isinstance(op, dict) and isinstance(op.get("id"), str)]
    if len(planned_ids) != len(operations):
        errors.append("every planning service operation must have a text id")
    for duplicate, count in sorted(Counter(planned_ids).items()):
        if count > 1:
            errors.append(f"duplicate planning service operation id: {duplicate}")
    expected = {service_target(operation_id) for operation_id in planned_ids}
    actual: set[tuple[object, ...]] = set()

    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {kind for kind in requirement.get("requiredPositiveProofKinds", []) if isinstance(kind, str)}
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "service_interface":
                continue
            actual.add(key)
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "operation":
                errors.append(
                    f"service planning requirement {requirement_id!r} has unsupported target {key}; "
                    "service planning targets must be contract-item/service_interface/operation"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"service planning requirement {requirement_id!r} targets operation {key[3]!r} "
                    f"and must declare an executable requiredPositiveProofKinds value from {sorted(EXECUTABLE_PROOF_KINDS)}"
                )
    for missing in sorted(expected - actual, key=str):
        errors.append(f"planned service operation is missing a planning requirement target: {missing}")
    for unknown in sorted(actual - expected, key=str):
        if unknown[0] == "contract-item" and unknown[2] == "operation":
            errors.append(f"service planning requirement targets undeclared planned operation: {unknown}")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        contract = load_json(root, SERVICE_CONTRACT)
        evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    except (OSError, ValueError, TypeError) as exc:
        return [str(exc)]

    service_mode = contract.get("mode")
    evidence_mode = evidence.get("mode")
    if evidence_mode == "planning":
        if service_mode != "planning":
            return [
                "planning implementation evidence requires contracts/service-interface.json to be in planning mode so service operation IDs are authoritative before coding"
            ]
        return planning_requirement_errors(contract, evidence)
    if service_mode == "planning":
        return ["planning service contract requires planning implementation evidence"]
    if service_mode == "template":
        if evidence_mode == "product":
            errors.append(
                "capability.service is selected but contracts/service-interface.json remains in template mode while product implementation evidence is active; either remove capability.service from Composition intent or declare the service contract in product mode and add executable service evidence"
            )
        return errors
    if service_mode != "product":
        return ["contracts/service-interface.json mode must be template, planning, or product"]
    if evidence_mode != "product":
        return ["product service contract requires product implementation evidence"]

    operations = contract.get("operations")
    if not isinstance(operations, list):
        return ["product service contract operations must be a list"]
    operation_ids = [entry.get("id") for entry in operations if isinstance(entry, dict)]
    duplicates = sorted(key for key, count in Counter(operation_ids).items() if key is not None and count > 1)
    if duplicates:
        errors.append(f"duplicate service operation ids: {duplicates}")

    expected = {
        ("contract-item", "service_interface", "operation", operation_id)
        for operation_id in operation_ids
        if isinstance(operation_id, str)
    }
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(records, list):
        return errors + ["product implementation evidence records must be a list"]
    if not isinstance(requirements, list):
        return errors + ["product implementation evidence requirements must be a list"]

    service_records = [
        record for record in records
        if isinstance(record, dict)
        and isinstance(record.get("target"), dict)
        and record["target"].get("contractId") == "service_interface"
    ]
    by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in service_records:
        by_target.setdefault(target_key(record.get("target")), []).append(record)

    actual = set(by_target)
    for missing in sorted(expected - actual, key=str):
        errors.append(f"missing service implementation-evidence target: {missing}")
    for unknown in sorted(actual - expected, key=str):
        errors.append(f"unknown service implementation-evidence target: {unknown}")

    requirement_records: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for record_id in requirement.get("recordIds", []):
            if isinstance(record_id, str):
                requirement_records.setdefault(record_id, []).append(requirement)

    for key in sorted(expected, key=str):
        matches = by_target.get(key, [])
        if len(matches) != 1:
            if len(matches) > 1:
                errors.append(f"service target {key} must have exactly one record; found {len(matches)}")
            continue
        record = matches[0]
        record_id = record.get("id")
        for field, label in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            if not executable_proof_present(record, field):
                errors.append(
                    f"service record {record_id!r} requires verified {label} executable proof kind from {sorted(EXECUTABLE_PROOF_KINDS)}; static inspection or unit-only proof is insufficient"
                )
        linked = requirement_records.get(record_id, []) if isinstance(record_id, str) else []
        if not linked:
            errors.append(f"service record {record_id!r} must be linked from a product requirement")
            continue
        if not any(
            isinstance(requirement.get("requiredPositiveProofKinds"), list)
            and EXECUTABLE_PROOF_KINDS.intersection(requirement["requiredPositiveProofKinds"])
            for requirement in linked
        ):
            errors.append(
                f"service record {record_id!r} requires a linked requirement whose requiredPositiveProofKinds includes one of {sorted(EXECUTABLE_PROOF_KINDS)}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    if evidence.get("mode") == "planning":
        print("Service planned operation authority and executable proof strength: OK")
    else:
        print("Service interface coverage and executable evidence strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
