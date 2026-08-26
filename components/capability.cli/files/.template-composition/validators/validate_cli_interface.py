#!/usr/bin/env python3
"""Validate selected packaged CLI contracts and executable evidence strength."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CLI_CONTRACT = Path("contracts/cli-interface.json")
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
    return (
        target.get("kind"),
        target.get("contractId"),
        target.get("itemKind"),
        target.get("itemId"),
    )


def entrypoint_target(entrypoint_id: str) -> tuple[str, str, str, str]:
    return ("contract-item", "cli_interface", "entrypoint", entrypoint_id)


def proof_kinds(record: dict[str, Any], field: str) -> set[str]:
    proofs = record.get(field)
    if not isinstance(proofs, list):
        return set()
    return {
        proof.get("kind")
        for proof in proofs
        if isinstance(proof, dict) and isinstance(proof.get("kind"), str)
    }



def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    errors: list[str] = []
    allowed = ", ".join(sorted(EXECUTABLE_PROOF_KINDS))
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "cli_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "entrypoint":
                errors.append(
                    f"CLI planning requirement {requirement_id!r} has unsupported target {key}; "
                    "CLI planning targets must be contract-item/cli_interface/entrypoint"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"CLI planning requirement {requirement_id!r} targets entrypoint "
                    f"{key[3]!r} and must declare an executable requiredPositiveProofKinds "
                    f"value ({allowed})"
                )
    return errors

def validate(root: Path) -> list[str]:
    contract = load_json(root, CLI_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    cli_mode = contract.get("mode")
    evidence_mode = evidence.get("mode")

    if evidence_mode == "planning":
        return planning_requirement_errors(evidence)

    if cli_mode == "template":
        if evidence_mode == "product":
            return [
                "capability.cli is selected but contracts/cli-interface.json remains "
                "in template mode while product implementation evidence is active; "
                "either remove capability.cli from Composition intent or declare the "
                "CLI contract in product mode and add executable CLI evidence"
            ]
        return []
    if cli_mode != "product":
        return [f"unsupported CLI interface mode: {cli_mode!r}"]
    if evidence_mode != "product":
        return [
            "product CLI interface requires product implementation evidence; switch "
            "contracts/implementation-evidence.json to product mode and prove each "
            "CLI entrypoint"
        ]

    entrypoints = contract.get("entrypoints")
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(entrypoints, list):
        return ["CLI interface entrypoints must be an array"]
    if not isinstance(records, list):
        return ["implementation-evidence records must be an array"]
    if not isinstance(requirements, list):
        return ["implementation-evidence requirements must be an array"]

    errors: list[str] = []
    ids = [
        item.get("id")
        for item in entrypoints
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if len(ids) != len(entrypoints):
        errors.append("every product CLI entrypoint must have a text id")
    seen: set[str] = set()
    duplicates: set[str] = set()
    for entrypoint_id in ids:
        if entrypoint_id in seen:
            duplicates.add(entrypoint_id)
        seen.add(entrypoint_id)
    for duplicate in sorted(duplicates):
        errors.append(f"duplicate CLI entrypoint id: {duplicate}")

    for item in entrypoints:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        exit_codes = item.get("exitCodes")
        if isinstance(exit_codes, dict):
            values = [
                value
                for value in exit_codes.values()
                if isinstance(value, int) and not isinstance(value, bool)
            ]
            if len(values) != len(set(values)):
                errors.append(
                    f"CLI entrypoint {item['id']!r} assigns one exit code to "
                    "multiple meanings"
                )

    records_by_target: dict[
        tuple[object, ...], list[dict[str, Any]]
    ] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = target_key(record.get("target"))
        if len(key) >= 2 and key[1] == "cli_interface":
            records_by_target.setdefault(key, []).append(record)

    expected = {entrypoint_target(entrypoint_id) for entrypoint_id in ids}
    actual = set(records_by_target)
    for missing in sorted(expected - actual, key=str):
        errors.append(f"missing CLI implementation-evidence target: {missing}")
    for extra in sorted(actual - expected, key=str):
        if extra[0] == "contract-item":
            errors.append(f"unknown CLI implementation-evidence target: {extra}")
    for key, matching in sorted(
        records_by_target.items(), key=lambda item: str(item[0])
    ):
        if key in expected and len(matching) != 1:
            errors.append(
                f"CLI implementation-evidence target {key} must have exactly one record"
            )

    allowed = ", ".join(sorted(EXECUTABLE_PROOF_KINDS))
    requirement_refs: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        refs = requirement.get("recordIds")
        if not isinstance(refs, list):
            continue
        for record_id in refs:
            if isinstance(record_id, str):
                requirement_refs.setdefault(record_id, []).append(requirement)

    for key in sorted(expected & actual, key=str):
        matching = records_by_target[key]
        if len(matching) != 1:
            continue
        record = matching[0]
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append(
                f"CLI implementation-evidence target {key} must have a text record id"
            )
            continue
        for field, label in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            if proof_kinds(record, field).isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"CLI target {key} requires at least one {label} executable "
                    f"proof kind ({allowed}); static inspection or unit-only proof "
                    "is insufficient"
                )
        linked = requirement_refs.get(record_id, [])
        strong = False
        for requirement in linked:
            kinds = requirement.get("requiredPositiveProofKinds")
            declared = (
                {kind for kind in kinds if isinstance(kind, str)}
                if isinstance(kinds, list)
                else set()
            )
            if not declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                strong = True
                break
        if not strong:
            errors.append(
                f"CLI record {record_id!r} must be linked from at least one "
                "requirement whose requiredPositiveProofKinds includes an executable "
                f"CLI proof kind ({allowed})"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        errors = validate(root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate CLI interface: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    contract = load_json(root, CLI_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    if evidence.get("mode") == "planning":
        print("CLI planning targets and executable proof strength: OK")
    elif contract.get("mode") == "template":
        print("CLI interface: template mode OK; no product CLI claim is active")
    else:
        print("CLI interface and executable evidence strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
