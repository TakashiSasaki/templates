#!/usr/bin/env python3
"""Validate generic implementation-evidence semantics after schema validation."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from contract_common import contract_entries, load_json, load_manifest


REUSE_FAMILY_THRESHOLD = 3


def _duplicates(values: list[Any]) -> set[Any]:
    seen: set[Any] = set()
    out: set[Any] = set()
    for value in values:
        if value in seen:
            out.add(value)
        seen.add(value)
    return out


def _target_family(target: dict[str, Any]) -> tuple[str, str]:
    contract_id = target.get("contractId")
    target_kind = target.get("kind")
    if target_kind == "contract-item":
        family = target.get("itemKind")
    elif target_kind == "contract-transition":
        family = "contract-transition"
    else:
        family = target_kind
    return str(contract_id), str(family)


def proof_reuse_warnings(records: list[dict[str, Any]]) -> list[str]:
    """Return non-fatal diagnostics for suspiciously broad exact proof reuse.

    One parameterized or end-to-end proof may legitimately cover many items in the same
    contract family. A warning is therefore emitted only when the exact same proof
    execution signature is reused across at least three distinct contract/item families.
    """

    usages: dict[
        tuple[str, str, str, str, str],
        list[tuple[tuple[str, str], str, str]],
    ] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id"))
        target = record.get("target")
        if not isinstance(target, dict):
            continue
        family = _target_family(target)
        for polarity, key in (
            ("positive", "positiveEvidence"),
            ("negative", "negativeEvidence"),
        ):
            proofs = record.get(key, [])
            if not isinstance(proofs, list):
                continue
            for proof in proofs:
                if not isinstance(proof, dict):
                    continue
                signature = (
                    polarity,
                    str(proof.get("kind")),
                    str(proof.get("locator")),
                    str(proof.get("commandId")),
                    str(proof.get("expectedResult")),
                )
                usages[signature].append(
                    (family, record_id, str(proof.get("id")))
                )

    warnings: list[str] = []
    for signature in sorted(usages):
        entries = usages[signature]
        families = sorted({family for family, _, _ in entries})
        if len(families) < REUSE_FAMILY_THRESHOLD:
            continue
        polarity, proof_kind, locator, command_id, expected_result = signature
        family_text = ", ".join(
            f"{contract_id}/{family}" for contract_id, family in families
        )
        record_text = ", ".join(sorted({record_id for _, record_id, _ in entries}))
        proof_text = ", ".join(sorted({proof_id for _, _, proof_id in entries}))
        warnings.append(
            "broad implementation-evidence proof reuse: "
            f"{polarity} {proof_kind} proof at {locator!r} via command "
            f"{command_id!r} with expected result {expected_result!r} is reused "
            f"across {len(families)} target families [{family_text}] "
            f"by records [{record_text}] and proofs [{proof_text}]; this is not "
            "invalid by itself, but verify that the shared proof actually exercises "
            "each claimed target rather than merely providing generic validation"
        )
    return warnings


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(root)
        evidence = load_json(root / "contracts/implementation-evidence.json")
    except Exception as exc:
        return [f"cannot load implementation evidence: {exc}"]
    if not isinstance(evidence, dict):
        return ["implementation evidence must be an object"]

    commands = evidence.get("commands", [])
    gates = evidence.get("releaseGates", [])
    records = evidence.get("records", [])
    mode = evidence.get("mode")
    command_ids = [entry.get("id") for entry in commands]
    gate_ids = [entry.get("id") for entry in gates]
    record_ids = [entry.get("id") for entry in records]
    for label, values in (
        ("command", command_ids),
        ("release gate", gate_ids),
        ("record", record_ids),
    ):
        for duplicate in sorted(_duplicates(values)):
            errors.append(f"duplicate implementation-evidence {label} id: {duplicate}")

    known_commands = set(command_ids)
    known_gates = set(gate_ids)
    known_contracts = contract_entries(manifest)
    used_commands: set[Any] = set()
    used_gates: set[Any] = set()
    proof_ids: list[Any] = []
    gate_commands: dict[Any, set[Any]] = {}
    for gate in gates:
        refs = set(gate.get("commandIds", []))
        gate_commands[gate["id"]] = refs
        for missing in sorted(refs - known_commands):
            errors.append(f"release gate {gate['id']}: unknown command {missing}")

    if mode == "template":
        if commands or gates or records:
            errors.append("template implementation evidence must be empty")
        return errors
    if mode != "product":
        return [f"unsupported implementation-evidence mode: {mode!r}"]

    for record in records:
        owner = f"record {record['id']}"
        target = record.get("target", {})
        contract_id = target.get("contractId")
        if contract_id not in known_contracts:
            errors.append(f"{owner}: unknown contract target {contract_id}")
        elif target.get("kind") == "contract-transition":
            transitions = {
                (entry["version"] - 1, entry["version"])
                for entry in known_contracts[contract_id]["versionHistory"][1:]
            }
            pair = (target.get("fromVersion"), target.get("toVersion"))
            if pair not in transitions:
                errors.append(
                    f"{owner}: unknown contract transition {contract_id} {pair}"
                )

        gate_refs = set(record.get("releaseGateIds", []))
        used_gates.update(gate_refs)
        for missing in sorted(gate_refs - known_gates):
            errors.append(f"{owner}: unknown release gate {missing}")

        record_commands: set[Any] = set()
        proofs = list(record.get("positiveEvidence", [])) + list(
            record.get("negativeEvidence", [])
        )
        proof_ids.extend(proof.get("id") for proof in proofs)
        for proof in proofs:
            command_id = proof.get("commandId")
            if command_id:
                used_commands.add(command_id)
                record_commands.add(command_id)
                if command_id not in known_commands:
                    errors.append(
                        f"{owner} proof {proof.get('id')}: unknown command {command_id}"
                    )

        gated: set[Any] = set()
        for gate_id in gate_refs:
            gated.update(gate_commands.get(gate_id, set()))
        for command_id in sorted(record_commands - gated):
            errors.append(
                f"{owner}: proof command {command_id} is not executed by a selected release gate"
            )

    for duplicate in sorted(_duplicates(proof_ids)):
        errors.append(f"duplicate implementation-evidence proof id: {duplicate}")
    for unused in sorted(known_gates - used_gates):
        errors.append(f"unused implementation-evidence release gate: {unused}")
    for refs in gate_commands.values():
        used_commands.update(refs)
    for unused in sorted(known_commands - used_commands):
        errors.append(f"unused implementation-evidence command: {unused}")
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

    evidence = load_json(root / "contracts/implementation-evidence.json")
    if isinstance(evidence, dict) and evidence.get("mode") == "product":
        records = evidence.get("records", [])
        if isinstance(records, list):
            for warning in proof_reuse_warnings(records):
                print(f"WARNING: {warning}")
    print("Implementation evidence validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
