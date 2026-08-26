#!/usr/bin/env python3
"""Validate MCP Apps resource/association coverage and proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

APPS_CONTRACT = Path("contracts/mcp-apps.json")
MCP_CONTRACT = Path("contracts/mcp-interface.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
EXTENSION_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})
VIEW_PROOF_KINDS = frozenset({"accessibility-test", "end-to-end-test"})
ASSOCIATION_PROOF_KINDS = frozenset({"end-to-end-test"})


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def target_key(target: object) -> tuple[object, ...]:
    if not isinstance(target, dict):
        return (None, None, None, None)
    return (target.get("kind"), target.get("contractId"), target.get("itemKind"), target.get("itemId"))


def evidence_target(item_kind: str, item_id: str) -> tuple[str, str, str, str]:
    return ("contract-item", "mcp_apps", item_kind, item_id)


def proof_kinds(record: dict[str, Any], field: str) -> set[str]:
    proofs = record.get(field)
    if not isinstance(proofs, list):
        return set()
    return {p.get("kind") for p in proofs if isinstance(p, dict) and isinstance(p.get("kind"), str)}



def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    policies = {
        "extension": EXTENSION_PROOF_KINDS,
        "view": VIEW_PROOF_KINDS,
        "association": ASSOCIATION_PROOF_KINDS,
    }
    errors: list[str] = []
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
            if key[1] != "mcp_apps":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            item_kind = key[2]
            allowed = policies.get(item_kind)
            if key[0] != "contract-item" or allowed is None:
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} has unsupported "
                    f"target {key}; Apps planning targets must be extension, view, or association items"
                )
                continue
            if item_kind == "extension" and key[3] != "mcp-apps":
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} must use the stable "
                    "extension target id 'mcp-apps'"
                )
            if declared.isdisjoint(allowed):
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} targets {item_kind} "
                    f"{key[3]!r} and must declare compatible requiredPositiveProofKinds "
                    f"({', '.join(sorted(allowed))})"
                )
    return errors

def validate(root: Path) -> list[str]:
    apps = load_json(root, APPS_CONTRACT)
    mcp = load_json(root, MCP_CONTRACT)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    apps_mode = apps.get("mode")
    evidence_mode = evidence.get("mode")

    if evidence_mode == "planning":
        return planning_requirement_errors(evidence)

    if apps_mode == "template":
        if evidence_mode == "product":
            return ["capability.mcp-apps is selected but contracts/mcp-apps.json remains in template mode while product implementation evidence is active; either remove capability.mcp-apps or declare the Apps contract in product mode"]
        return []
    if apps_mode != "product":
        return [f"unsupported MCP Apps mode: {apps_mode!r}"]
    if evidence_mode != "product":
        return ["product MCP Apps contract requires product implementation evidence"]
    if mcp.get("mode") != "product":
        return ["product MCP Apps contract requires contracts/mcp-interface.json to be in product mode"]

    errors: list[str] = []
    extension = apps.get("extension")
    views = apps.get("views")
    associations = apps.get("associations")
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    operations = mcp.get("operations")
    if not isinstance(extension, dict):
        return ["MCP Apps product contract requires an extension object"]
    if not isinstance(views, list) or not isinstance(associations, list):
        return ["MCP Apps views and associations must be arrays"]
    if not isinstance(records, list) or not isinstance(requirements, list):
        return ["implementation-evidence records and requirements must be arrays"]
    if not isinstance(operations, list):
        return ["core MCP operations must be an array"]

    view_ids: list[str] = []
    uris: list[str] = []
    for view in views:
        if not isinstance(view, dict):
            errors.append("every MCP Apps view must be an object")
            continue
        vid = view.get("id")
        uri = view.get("resourceUri")
        if isinstance(vid, str):
            view_ids.append(vid)
        if isinstance(uri, str):
            uris.append(uri)
    for value, count in sorted(Counter(view_ids).items()):
        if count > 1: errors.append(f"duplicate MCP Apps view id: {value}")
    for value, count in sorted(Counter(uris).items()):
        if count > 1: errors.append(f"duplicate MCP Apps resource URI: {value}")
    view_set = set(view_ids)

    tool_operations = {op.get("id") for op in operations if isinstance(op, dict) and op.get("kind") == "tool" and isinstance(op.get("id"), str)}
    association_ids: list[str] = []
    operation_refs: list[str] = []
    referenced_views: set[str] = set()
    for assoc in associations:
        if not isinstance(assoc, dict):
            errors.append("every MCP Apps association must be an object")
            continue
        aid, operation_id, view_id = assoc.get("id"), assoc.get("operationId"), assoc.get("viewId")
        if isinstance(aid, str): association_ids.append(aid)
        if isinstance(operation_id, str): operation_refs.append(operation_id)
        if not isinstance(operation_id, str) or operation_id not in tool_operations:
            errors.append(f"MCP Apps association {aid!r} references unknown or non-tool MCP operation {operation_id!r}")
        if not isinstance(view_id, str) or view_id not in view_set:
            errors.append(f"MCP Apps association {aid!r} references unknown view {view_id!r}")
        elif isinstance(view_id, str):
            referenced_views.add(view_id)
    for value, count in sorted(Counter(association_ids).items()):
        if count > 1: errors.append(f"duplicate MCP Apps association id: {value}")
    for value, count in sorted(Counter(operation_refs).items()):
        if count > 1: errors.append(f"MCP tool operation has multiple Apps associations: {value}")
    for vid in sorted(view_set - referenced_views):
        errors.append(f"MCP Apps view {vid!r} is not referenced by any tool association")

    expected: dict[tuple[str, str, str, str], frozenset[str]] = {
        evidence_target("extension", "mcp-apps"): EXTENSION_PROOF_KINDS
    }
    expected.update({evidence_target("view", vid): VIEW_PROOF_KINDS for vid in view_ids})
    expected.update({evidence_target("association", aid): ASSOCIATION_PROOF_KINDS for aid in association_ids})

    records_by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in records:
        if isinstance(record, dict):
            key = target_key(record.get("target"))
            if len(key) >= 2 and key[1] == "mcp_apps":
                records_by_target.setdefault(key, []).append(record)
    actual = set(records_by_target)
    for missing in sorted(set(expected) - actual, key=str): errors.append(f"missing MCP Apps implementation-evidence target: {missing}")
    for extra in sorted(actual - set(expected), key=str): errors.append(f"unknown MCP Apps implementation-evidence target: {extra}")

    requirement_refs: dict[str, list[dict[str, Any]]] = {}
    for req in requirements:
        if isinstance(req, dict) and isinstance(req.get("recordIds"), list):
            for record_id in req["recordIds"]:
                if isinstance(record_id, str): requirement_refs.setdefault(record_id, []).append(req)

    for key, allowed in expected.items():
        matching = records_by_target.get(key, [])
        if len(matching) != 1:
            if len(matching) > 1: errors.append(f"MCP Apps implementation-evidence target {key} must have exactly one record")
            continue
        record = matching[0]
        allowed_text = ", ".join(sorted(allowed))
        for field, polarity in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            if proof_kinds(record, field).isdisjoint(allowed):
                errors.append(f"MCP Apps {key[2]} {key[3]!r} requires at least one {polarity} proof kind ({allowed_text})")
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append(f"MCP Apps target {key} must have a text evidence record id")
            continue
        linked = requirement_refs.get(record_id, [])
        if not linked:
            errors.append(f"MCP Apps record {record_id!r} must be linked from at least one product requirement")
        elif not any(isinstance(req.get("requiredPositiveProofKinds"), list) and not allowed.isdisjoint(req["requiredPositiveProofKinds"]) for req in linked):
            errors.append(f"MCP Apps record {record_id!r} must be linked from a requirement declaring compatible proof strength ({allowed_text})")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    root = Path(parser.parse_args().root).resolve()
    try:
        errors = validate(root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate MCP Apps: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors: print(f"ERROR: {error}", file=sys.stderr)
        return 1
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    if evidence.get("mode") == "planning":
        print("MCP Apps planning targets and proof strength: OK")
    else:
        print("MCP Apps contract/evidence coverage: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
