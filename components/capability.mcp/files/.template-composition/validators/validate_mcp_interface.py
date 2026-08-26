#!/usr/bin/env python3
"""Validate selected MCP transport/operation coverage and executable proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MCP_CONTRACT = Path("contracts/mcp-interface.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
EXECUTABLE_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})
SUPPORTED_PROTOCOL_REVISION = "2026-07-28"
SUPPORTED_TRANSPORT_KINDS = frozenset({"stdio", "streamable-http"})
SUPPORTED_OPERATION_KINDS = frozenset(
    {"tool", "resource", "prompt", "protocol-operation"}
)


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


def proof_kinds(record: dict[str, Any], field: str) -> set[str]:
    proofs = record.get(field)
    if not isinstance(proofs, list):
        return set()
    return {
        proof.get("kind")
        for proof in proofs
        if isinstance(proof, dict) and isinstance(proof.get("kind"), str)
    }


def evidence_target(item_kind: str, item_id: str) -> tuple[str, str, str, str]:
    return ("contract-item", "mcp_interface", item_kind, item_id)



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
            if key[1] != "mcp_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] not in {"transport", "operation"}:
                errors.append(
                    f"MCP planning requirement {requirement_id!r} has unsupported target {key}; "
                    "MCP planning targets must be transport or operation contract items"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"MCP planning requirement {requirement_id!r} targets {key[2]} "
                    f"{key[3]!r} and must declare an executable requiredPositiveProofKinds "
                    f"value ({allowed})"
                )
    return errors

def validate(root: Path) -> list[str]:
    contract = load_json(root, MCP_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    mcp_mode = contract.get("mode")
    evidence_mode = evidence.get("mode")

    if evidence_mode == "planning":
        return planning_requirement_errors(evidence)

    if mcp_mode == "template":
        if evidence_mode == "product":
            return [
                "capability.mcp is selected but contracts/mcp-interface.json remains "
                "in template mode while product implementation evidence is active; "
                "either remove capability.mcp from Composition intent or declare the "
                "MCP interface contract in product mode and add transport/operation evidence"
            ]
        return []
    if mcp_mode != "product":
        return [f"unsupported MCP interface mode: {mcp_mode!r}"]
    if evidence_mode != "product":
        return [
            "product MCP interface contract requires product implementation evidence; "
            "switch contracts/implementation-evidence.json to product mode and prove "
            "every declared transport and operation"
        ]

    errors: list[str] = []
    if contract.get("protocolRevision") != SUPPORTED_PROTOCOL_REVISION:
        errors.append(
            "MCP product contract protocolRevision must be "
            f"{SUPPORTED_PROTOCOL_REVISION!r} for schema v1"
        )

    transports = contract.get("transports")
    operations = contract.get("operations")
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(transports, list):
        return errors + ["MCP transports must be an array"]
    if not isinstance(operations, list):
        return errors + ["MCP operations must be an array"]
    if not isinstance(records, list):
        return errors + ["implementation-evidence records must be an array"]
    if not isinstance(requirements, list):
        return errors + ["implementation-evidence requirements must be an array"]

    transport_ids: list[str] = []
    transport_by_id: dict[str, dict[str, Any]] = {}
    for transport in transports:
        if not isinstance(transport, dict):
            errors.append("every product MCP transport must be an object")
            continue
        transport_id = transport.get("id")
        transport_kind = transport.get("kind")
        if not isinstance(transport_id, str):
            errors.append("every product MCP transport must have a text id")
            continue
        transport_ids.append(transport_id)
        transport_by_id.setdefault(transport_id, transport)
        if transport_kind not in SUPPORTED_TRANSPORT_KINDS:
            errors.append(
                f"MCP transport {transport_id!r} has unsupported kind {transport_kind!r}"
            )
    for duplicate, count in sorted(Counter(transport_ids).items()):
        if count > 1:
            errors.append(f"duplicate MCP transport id: {duplicate}")

    operation_ids: list[str] = []
    exposure_keys: list[tuple[str, str, str]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            errors.append("every product MCP operation must be an object")
            continue
        operation_id = operation.get("id")
        operation_kind = operation.get("kind")
        operation_name = operation.get("name")
        transport_id = operation.get("transportId")
        if not isinstance(operation_id, str):
            errors.append("every product MCP operation must have a text id")
            continue
        operation_ids.append(operation_id)
        if operation_kind not in SUPPORTED_OPERATION_KINDS:
            errors.append(
                f"MCP operation {operation_id!r} has unsupported kind {operation_kind!r}"
            )
        if not isinstance(transport_id, str) or transport_id not in transport_by_id:
            errors.append(
                f"MCP operation {operation_id!r} references unknown transportId "
                f"{transport_id!r}"
            )
        if (
            isinstance(transport_id, str)
            and isinstance(operation_kind, str)
            and isinstance(operation_name, str)
        ):
            exposure_keys.append((transport_id, operation_kind, operation_name))
    for duplicate, count in sorted(Counter(operation_ids).items()):
        if count > 1:
            errors.append(f"duplicate MCP operation id: {duplicate}")
    for duplicate, count in sorted(Counter(exposure_keys).items()):
        if count > 1:
            errors.append(
                "duplicate MCP operation exposure: "
                f"transport={duplicate[0]!r} kind={duplicate[1]!r} name={duplicate[2]!r}"
            )

    expected = {
        evidence_target("transport", transport_id) for transport_id in transport_ids
    }
    expected.update(
        evidence_target("operation", operation_id) for operation_id in operation_ids
    )

    records_by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = target_key(record.get("target"))
        if len(key) >= 2 and key[1] == "mcp_interface":
            records_by_target.setdefault(key, []).append(record)

    actual = set(records_by_target)
    for missing in sorted(expected - actual, key=str):
        errors.append(f"missing MCP implementation-evidence target: {missing}")
    for extra in sorted(actual - expected, key=str):
        errors.append(f"unknown MCP implementation-evidence target: {extra}")
    for key, matching in sorted(records_by_target.items(), key=lambda item: str(item[0])):
        if key in expected and len(matching) != 1:
            errors.append(
                f"MCP implementation-evidence target {key} must have exactly one record"
            )

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

    allowed = ", ".join(sorted(EXECUTABLE_PROOF_KINDS))
    for key in sorted(expected & actual, key=str):
        matching = records_by_target[key]
        if len(matching) != 1:
            continue
        record = matching[0]
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append(f"MCP target {key} must have a text implementation-evidence record id")
            continue
        for field, polarity in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            if proof_kinds(record, field).isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"MCP {key[2]} {key[3]!r} requires at least one {polarity} "
                    f"executable proof kind ({allowed}); static inspection or unit-only "
                    "proof is insufficient"
                )
        linked = requirement_refs.get(record_id, [])
        if not linked:
            errors.append(
                f"MCP record {record_id!r} must be linked from at least one product requirement"
            )
            continue
        if not any(
            isinstance(requirement.get("requiredPositiveProofKinds"), list)
            and not EXECUTABLE_PROOF_KINDS.isdisjoint(
                requirement["requiredPositiveProofKinds"]
            )
            for requirement in linked
        ):
            errors.append(
                f"MCP record {record_id!r} must be linked from at least one requirement "
                "whose requiredPositiveProofKinds includes an executable proof kind "
                f"({allowed})"
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
        print(f"ERROR: cannot validate MCP interface: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    contract = load_json(root, MCP_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    if evidence.get("mode") == "planning":
        print("MCP planning targets and executable proof strength: OK")
    elif contract.get("mode") == "template":
        print("MCP interface: template mode OK; no product transport/operation claim is active")
    else:
        print("MCP transport/operation coverage and executable proof strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
