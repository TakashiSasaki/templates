#!/usr/bin/env python3
"""Validate Website implementation-evidence coverage and browser proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .website_evidence_targets import BROWSER_LEVEL_PROOF_KINDS, expected_targets, requires_browser_level_proof, target_key
else:
    from website_evidence_targets import BROWSER_LEVEL_PROOF_KINDS, expected_targets, requires_browser_level_proof, target_key


def load(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain an object")
    return value


def command_capabilities(evidence: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for command in evidence.get("commands", []):
        if not isinstance(command, dict) or not isinstance(command.get("id"), str):
            continue
        execution = command.get("execution")
        capabilities = execution.get("capabilities") if isinstance(execution, dict) else []
        result[command["id"]] = {item for item in capabilities if isinstance(item, str)} if isinstance(capabilities, list) else set()
    return result


def browser_backed(proofs: object, capabilities: dict[str, set[str]]) -> bool:
    return isinstance(proofs, list) and any(
        isinstance(proof, dict)
        and proof.get("kind") in BROWSER_LEVEL_PROOF_KINDS
        and isinstance(proof.get("commandId"), str)
        and "browser" in capabilities.get(proof["commandId"], set())
        for proof in proofs
    )


def validate(root: Path) -> list[str]:
    evidence = load(root, "contracts/implementation-evidence.json")
    mode = evidence.get("mode")
    if mode == "template":
        return []
    expected = {target_key(target): target for target in expected_targets(root)}
    errors: list[str] = []

    if mode == "planning":
        seen: set[tuple[Any, ...]] = set()
        for requirement in evidence.get("requirements", []):
            if not isinstance(requirement, dict):
                continue
            targets = requirement.get("targets")
            target_list = [item for item in targets if isinstance(item, dict)] if isinstance(targets, list) else []
            declared = {item for item in requirement.get("requiredPositiveProofKinds", []) if isinstance(item, str)}
            for target in target_list:
                key = target_key(target)
                if key not in expected:
                    errors.append(f"unknown planning Website evidence target: {key}")
                    continue
                seen.add(key)
                if requires_browser_level_proof(target) and declared.isdisjoint(BROWSER_LEVEL_PROOF_KINDS):
                    errors.append(f"browser-sensitive planning Website target {key} requires one of {BROWSER_LEVEL_PROOF_KINDS} in requiredPositiveProofKinds")
        for key in sorted(set(expected) - seen, key=repr):
            errors.append(f"missing planning Website evidence target: {key}")
        return errors

    if mode != "product":
        return [f"unsupported Website implementation-evidence mode: {mode!r}"]

    records = evidence.get("records")
    record_list = [item for item in records if isinstance(item, dict) and isinstance(item.get("target"), dict)] if isinstance(records, list) else []
    actual_keys = [target_key(item["target"]) for item in record_list]
    for key in sorted(set(expected) - set(actual_keys), key=repr):
        errors.append(f"missing Website implementation-evidence target: {key}")
    for key in sorted(set(actual_keys) - set(expected), key=repr):
        errors.append(f"unknown Website implementation-evidence target: {key}")
    if len(actual_keys) != len(set(actual_keys)):
        errors.append("Website implementation evidence contains duplicate targets")

    capabilities = command_capabilities(evidence)
    browser_record_ids: set[str] = set()
    for record in record_list:
        target = record["target"]
        if not requires_browser_level_proof(target):
            continue
        record_id = record.get("id")
        if isinstance(record_id, str):
            browser_record_ids.add(record_id)
        key = target_key(target)
        if not browser_backed(record.get("positiveEvidence"), capabilities):
            errors.append(f"browser-sensitive Website target {key} requires positive browser-backed proof")
        if not browser_backed(record.get("negativeEvidence"), capabilities):
            errors.append(f"browser-sensitive Website target {key} requires negative browser-backed proof")

    for requirement in evidence.get("requirements", []):
        if not isinstance(requirement, dict):
            continue
        record_ids = {item for item in requirement.get("recordIds", []) if isinstance(item, str)}
        if record_ids & browser_record_ids:
            declared = {item for item in requirement.get("requiredPositiveProofKinds", []) if isinstance(item, str)}
            if declared.isdisjoint(BROWSER_LEVEL_PROOF_KINDS):
                errors.append(f"Website requirement {requirement.get('id')!r} links a browser-sensitive target and must require one of {BROWSER_LEVEL_PROOF_KINDS}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    try:
        errors = validate(Path(args.root).resolve())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate Website evidence: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Website implementation-evidence coverage: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
