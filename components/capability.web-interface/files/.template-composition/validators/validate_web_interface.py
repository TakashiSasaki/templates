#!/usr/bin/env python3
"""Validate selected standalone Web interface endpoint coverage and proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

WEB_INTERFACE_CONTRACT = Path("contracts/web-interface.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
BROWSER_PROOF_KINDS = frozenset({"accessibility-test", "end-to-end-test"})
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


def endpoint_target(endpoint_id: str) -> tuple[str, str, str, str]:
    return ("contract-item", "web_interface", "endpoint", endpoint_id)


def proof_kinds(record: dict[str, Any], field: str) -> set[str]:
    proofs = record.get(field)
    if not isinstance(proofs, list):
        return set()
    return {proof.get("kind") for proof in proofs if isinstance(proof, dict) and isinstance(proof.get("kind"), str)}


def required_proof_kinds(endpoint_kind: str) -> frozenset[str]:
    if endpoint_kind == "browser-page":
        return BROWSER_PROOF_KINDS
    return EXECUTABLE_PROOF_KINDS


def proof_label(endpoint_kind: str) -> str:
    return "browser-level" if endpoint_kind == "browser-page" else "executable"


def planning_requirement_errors(contract: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    endpoints = contract.get("endpoints")
    requirements = evidence.get("requirements")
    if not isinstance(endpoints, list):
        return ["planning Web interface endpoints must be an array"]
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]

    errors: list[str] = []
    endpoint_by_id: dict[str, dict[str, Any]] = {}
    endpoint_ids: list[str] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict) or not isinstance(endpoint.get("id"), str):
            errors.append("every planning Web interface endpoint must have a text id")
            continue
        endpoint_id = endpoint["id"]
        endpoint_ids.append(endpoint_id)
        endpoint_by_id.setdefault(endpoint_id, endpoint)
    for duplicate, count in sorted(Counter(endpoint_ids).items()):
        if count > 1:
            errors.append(f"duplicate planning Web interface endpoint id: {duplicate}")

    expected = {endpoint_target(endpoint_id) for endpoint_id in endpoint_ids}
    actual: set[tuple[object, ...]] = set()
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {kind for kind in requirement.get("requiredPositiveProofKinds", []) if isinstance(kind, str)}
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "web_interface":
                continue
            actual.add(key)
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "endpoint":
                errors.append(
                    f"Web interface planning requirement {requirement_id!r} has unsupported target {key}; planning targets must be contract-item/web_interface/endpoint"
                )
                continue
            endpoint = endpoint_by_id.get(key[3]) if isinstance(key[3], str) else None
            if endpoint is None:
                continue
            endpoint_kind = endpoint.get("kind")
            if endpoint_kind not in {"browser-page", "backend-api", "health"}:
                errors.append(f"planned Web interface endpoint {key[3]!r} has unsupported kind {endpoint_kind!r}")
                continue
            required = required_proof_kinds(endpoint_kind)
            if declared.isdisjoint(required):
                errors.append(
                    f"Web interface planning requirement {requirement_id!r} targets {endpoint_kind} endpoint {key[3]!r} and must declare a {proof_label(endpoint_kind)} requiredPositiveProofKinds value ({', '.join(sorted(required))})"
                )
    for missing in sorted(expected - actual, key=str):
        errors.append(f"planned Web interface endpoint is missing a planning requirement target: {missing}")
    for unknown in sorted(actual - expected, key=str):
        if unknown[0] == "contract-item" and unknown[2] == "endpoint":
            errors.append(f"Web interface planning requirement targets undeclared planned endpoint: {unknown}")
    return errors


def validate(root: Path) -> list[str]:
    contract = load_json(root, WEB_INTERFACE_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    interface_mode = contract.get("mode")
    evidence_mode = evidence.get("mode")

    if evidence_mode == "planning":
        if interface_mode != "planning":
            return [
                "planning implementation evidence requires contracts/web-interface.json to be in planning mode so endpoint IDs and browser/API kinds are authoritative before coding"
            ]
        return planning_requirement_errors(contract, evidence)
    if interface_mode == "planning":
        return ["planning Web interface contract requires planning implementation evidence"]

    if interface_mode == "template":
        if evidence_mode == "product":
            return [
                "capability.web-interface is selected but contracts/web-interface.json remains in template mode while product implementation evidence is active; either remove capability.web-interface from Composition intent or declare the Web interface contract in product mode and add endpoint evidence"
            ]
        return []
    if interface_mode != "product":
        return [f"unsupported Web interface mode: {interface_mode!r}"]
    if evidence_mode != "product":
        return [
            "product Web interface contract requires product implementation evidence; switch contracts/implementation-evidence.json to product mode and prove each declared endpoint"
        ]

    endpoints = contract.get("endpoints")
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(endpoints, list):
        return ["Web interface endpoints must be an array"]
    if not isinstance(records, list):
        return ["implementation-evidence records must be an array"]
    if not isinstance(requirements, list):
        return ["implementation-evidence requirements must be an array"]

    errors: list[str] = []
    endpoint_by_id: dict[str, dict[str, Any]] = {}
    endpoint_ids: list[str] = []
    address_keys: list[tuple[str, str]] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            errors.append("every product Web interface endpoint must be an object")
            continue
        endpoint_id = endpoint.get("id")
        endpoint_kind = endpoint.get("kind")
        method = endpoint.get("method")
        path = endpoint.get("path")
        if not isinstance(endpoint_id, str):
            errors.append("every product Web interface endpoint must have a text id")
            continue
        endpoint_ids.append(endpoint_id)
        endpoint_by_id.setdefault(endpoint_id, endpoint)
        if isinstance(method, str) and isinstance(path, str):
            address_keys.append((method, path))
        if endpoint_kind not in {"browser-page", "backend-api", "health"}:
            errors.append(f"Web interface endpoint {endpoint_id!r} has unsupported kind {endpoint_kind!r}")

    for duplicate, count in sorted(Counter(endpoint_ids).items()):
        if count > 1:
            errors.append(f"duplicate Web interface endpoint id: {duplicate}")
    for duplicate, count in sorted(Counter(address_keys).items()):
        if count > 1:
            errors.append(f"duplicate Web interface endpoint address: {duplicate[0]} {duplicate[1]}")

    records_by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = target_key(record.get("target"))
        if len(key) >= 2 and key[1] == "web_interface":
            records_by_target.setdefault(key, []).append(record)

    expected = {endpoint_target(endpoint_id) for endpoint_id in endpoint_ids}
    actual = set(records_by_target)
    for missing in sorted(expected - actual, key=str):
        errors.append(f"missing Web interface implementation-evidence target: {missing}")
    for extra in sorted(actual - expected, key=str):
        errors.append(f"unknown Web interface implementation-evidence target: {extra}")
    for key, matching in sorted(records_by_target.items(), key=lambda item: str(item[0])):
        if key in expected and len(matching) != 1:
            errors.append(f"Web interface implementation-evidence target {key} must have exactly one record")

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
        endpoint_id = key[3]
        endpoint = endpoint_by_id.get(endpoint_id)
        if endpoint is None:
            continue
        endpoint_kind = endpoint.get("kind")
        if not isinstance(endpoint_kind, str):
            continue
        required = required_proof_kinds(endpoint_kind)
        allowed = ", ".join(sorted(required))
        label = proof_label(endpoint_kind)
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append(f"Web interface target {key} must have a text implementation-evidence record id")
            continue
        for field, polarity in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            if proof_kinds(record, field).isdisjoint(required):
                errors.append(
                    f"Web interface endpoint {endpoint_id!r} ({endpoint_kind}) requires at least one {polarity} {label} proof kind ({allowed}); static inspection or unit-only proof is insufficient"
                )
        linked = requirement_refs.get(record_id, [])
        if not linked:
            errors.append(f"Web interface record {record_id!r} must be linked from at least one product requirement")
            continue
        if not any(
            isinstance(requirement.get("requiredPositiveProofKinds"), list)
            and not required.isdisjoint(requirement["requiredPositiveProofKinds"])
            for requirement in linked
        ):
            errors.append(
                f"Web interface record {record_id!r} must be linked from at least one requirement whose requiredPositiveProofKinds includes a {label} proof kind ({allowed})"
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
        print(f"ERROR: cannot validate Web interface: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    contract = load_json(root, WEB_INTERFACE_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    if evidence.get("mode") == "planning":
        print("Web interface planned endpoint authority and subtype proof strength: OK")
    elif contract.get("mode") == "template":
        print("Web interface: template mode OK; no product endpoint claim is active")
    else:
        print("Web interface endpoint coverage and proof strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
