#!/usr/bin/env python3
"""Validate selected PWA implementation-evidence coverage and browser proof strength."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
TARGET_HELPER = Path("scripts/pwa_evidence_targets.py")


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def load_target_helper(root: Path) -> Any:
    path = root / TARGET_HELPER
    spec = importlib.util.spec_from_file_location("_pwa_evidence_targets", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load PWA evidence target helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command_capabilities(evidence: dict[str, Any]) -> dict[str, set[str]]:
    commands = evidence.get("commands")
    if not isinstance(commands, list):
        return {}
    result: dict[str, set[str]] = {}
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("id"), str):
            continue
        execution = command.get("execution")
        capabilities = execution.get("capabilities") if isinstance(execution, dict) else None
        result[command["id"]] = (
            {item for item in capabilities if isinstance(item, str)}
            if isinstance(capabilities, list)
            else set()
        )
    return result


def browser_proof_kinds(record: dict[str, Any], field: str, allowed: set[str]) -> list[dict[str, Any]]:
    proofs = record.get(field)
    if not isinstance(proofs, list):
        return []
    return [
        proof
        for proof in proofs
        if isinstance(proof, dict) and proof.get("kind") in allowed
    ]


def planning_errors(
    evidence: dict[str, Any],
    helper: Any,
    expected: set[tuple[object, ...]],
) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]

    browser_kinds = set(helper.BROWSER_LEVEL_PROOF_KINDS)
    seen: set[tuple[object, ...]] = set()
    strong: set[tuple[object, ...]] = set()
    errors: list[str] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        requirement_id = requirement.get("id", f"index-{index}")
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        targets = requirement.get("targets")
        if not isinstance(targets, list):
            continue
        for target in targets:
            key = helper.target_key(target)
            if len(key) < 2 or key[1] not in helper.PWA_CONTRACT_IDS:
                continue
            seen.add(key)
            if key not in expected:
                errors.append(
                    f"PWA planning requirement {requirement_id!r} targets unknown proof family: {key}"
                )
                continue
            if not declared.isdisjoint(browser_kinds):
                strong.add(key)

    for key in sorted(expected - seen, key=str):
        errors.append(
            f"planned PWA proof family is missing an implementation-evidence requirement target: {helper.family_label(key)}"
        )
    for key in sorted(expected - strong, key=str):
        errors.append(
            f"planned PWA proof family {helper.family_label(key)} must be covered by a requirement whose requiredPositiveProofKinds includes a browser-level kind ({', '.join(sorted(browser_kinds))})"
        )
    return errors


def product_errors(
    evidence: dict[str, Any],
    helper: Any,
    expected: set[tuple[object, ...]],
) -> list[str]:
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(records, list):
        return ["product implementation-evidence records must be an array"]
    if not isinstance(requirements, list):
        return ["product implementation-evidence requirements must be an array"]

    errors: list[str] = []
    browser_kinds = set(helper.BROWSER_LEVEL_PROOF_KINDS)
    capabilities = command_capabilities(evidence)
    records_by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = helper.target_key(record.get("target"))
        if len(key) >= 2 and key[1] in helper.PWA_CONTRACT_IDS:
            records_by_target.setdefault(key, []).append(record)

    actual = set(records_by_target)
    for key in sorted(expected - actual, key=str):
        errors.append(f"missing PWA implementation-evidence target: {helper.family_label(key)}")
    for key in sorted(actual - expected, key=str):
        errors.append(f"unknown PWA implementation-evidence target: {key}")
    for key, matching in sorted(records_by_target.items(), key=lambda item: str(item[0])):
        if key in expected and len(matching) != 1:
            errors.append(
                f"PWA proof family {helper.family_label(key)} must have exactly one implementation-evidence record"
            )

    requirement_refs: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for record_id in requirement.get("recordIds", []):
            if isinstance(record_id, str):
                requirement_refs.setdefault(record_id, []).append(requirement)

    allowed_label = ", ".join(sorted(browser_kinds))
    for key in sorted(expected & actual, key=str):
        matching = records_by_target[key]
        if len(matching) != 1:
            continue
        record = matching[0]
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append(f"PWA proof family {helper.family_label(key)} must have a text record id")
            continue
        for field, polarity in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            browser_level = browser_proof_kinds(record, field, browser_kinds)
            browser_backed = [
                proof
                for proof in browser_level
                if "browser" in capabilities.get(proof.get("commandId"), set())
            ]
            for proof in browser_level:
                if "browser" not in capabilities.get(proof.get("commandId"), set()):
                    errors.append(
                        f"PWA {polarity} proof {proof.get('id')!r} for {helper.family_label(key)} uses browser-level proof kind {proof.get('kind')!r} but command {proof.get('commandId')!r} lacks browser execution capability"
                    )
            if not browser_backed:
                errors.append(
                    f"PWA proof family {helper.family_label(key)} requires at least one {polarity} browser-level proof kind ({allowed_label}) backed by an authoritative command with browser execution capability"
                )

        linked = requirement_refs.get(record_id, [])
        if not linked:
            errors.append(
                f"PWA evidence record {record_id!r} for {helper.family_label(key)} must be linked from at least one product requirement"
            )
            continue
        if not any(
            isinstance(requirement.get("requiredPositiveProofKinds"), list)
            and not browser_kinds.isdisjoint(requirement["requiredPositiveProofKinds"])
            for requirement in linked
        ):
            errors.append(
                f"PWA evidence record {record_id!r} for {helper.family_label(key)} must be linked from a requirement whose requiredPositiveProofKinds includes a browser-level kind ({allowed_label})"
            )
    return errors


def validate(root: Path) -> list[str]:
    helper = load_target_helper(root)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    pwa_mode = helper.pwa_mode(root)
    evidence_mode = evidence.get("mode")
    if evidence_mode != pwa_mode:
        return [
            f"PWA evidence coverage requires implementation-evidence mode {pwa_mode!r}; found {evidence_mode!r}"
        ]
    if pwa_mode == "template":
        return []

    expected = {helper.target_key(target) for target in helper.expected_targets(root)}
    if pwa_mode == "planning":
        return planning_errors(evidence, helper, expected)
    if pwa_mode == "product":
        return product_errors(evidence, helper, expected)
    return [f"unsupported PWA evidence mode: {pwa_mode!r}"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        errors = validate(root)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate PWA implementation evidence: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    helper = load_target_helper(root)
    mode = helper.pwa_mode(root)
    if mode == "template":
        print("PWA evidence coverage: template mode OK; no product PWA proof claim is active")
    elif mode == "planning":
        print("PWA planning proof-family coverage and browser proof strength: OK")
    else:
        print("PWA product proof-family coverage and browser proof strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
