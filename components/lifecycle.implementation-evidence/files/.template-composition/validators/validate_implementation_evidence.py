#!/usr/bin/env python3
"""Validate generic implementation-evidence structure and optional release readiness."""

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
    """Return non-fatal diagnostics for suspiciously broad exact proof reuse."""

    usages: dict[
        tuple[str, str, str, str, str, str],
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
                    str(proof.get("executionClass")),
                    str(proof.get("locator")),
                    str(proof.get("commandId")),
                    str(proof.get("expectedResult")),
                )
                usages[signature].append((family, record_id, str(proof.get("id"))))

    warnings: list[str] = []
    for signature in sorted(usages):
        entries = usages[signature]
        families = sorted({family for family, _, _ in entries})
        if len(families) < REUSE_FAMILY_THRESHOLD:
            continue
        polarity, proof_kind, execution_class, locator, command_id, expected_result = signature
        family_text = ", ".join(
            f"{contract_id}/{family}" for contract_id, family in families
        )
        record_text = ", ".join(sorted({record_id for _, record_id, _ in entries}))
        proof_text = ", ".join(sorted({proof_id for _, _, proof_id in entries}))
        warnings.append(
            "broad implementation-evidence proof reuse: "
            f"{polarity} {proof_kind}/{execution_class} proof at {locator!r} via command "
            f"{command_id!r} with expected result {expected_result!r} is reused "
            f"across {len(families)} target families [{family_text}] "
            f"by records [{record_text}] and proofs [{proof_text}]; this is not "
            "invalid by itself, but verify that the shared proof actually exercises "
            "each claimed target rather than merely providing generic validation"
        )
    return warnings


def requirement_traceability_errors(evidence: dict[str, Any]) -> list[str]:
    """Validate requirement identities and requirement -> record references.

    Requirement descriptions are intentionally opaque. Structural validation only
    checks graph identity and reference integrity; release completeness is handled by
    ``release_readiness_errors`` so required/deferred work can remain representable.
    """

    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["implementation-evidence requirements must be an array"]
    if evidence.get("mode") == "product" and not requirements:
        return ["product implementation evidence requires at least one explicit requirement"]

    records = evidence.get("records", [])
    if not isinstance(records, list):
        return ["implementation-evidence records must be an array"]
    records_by_id = {
        record.get("id"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }

    errors: list[str] = []
    requirement_ids = [
        requirement.get("id")
        for requirement in requirements
        if isinstance(requirement, dict)
    ]
    for duplicate in sorted(_duplicates(requirement_ids)):
        errors.append(f"duplicate implementation-evidence requirement id: {duplicate}")

    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            errors.append(f"requirement {index}: must be an object")
            continue
        requirement_id = requirement.get("id")
        owner = f"requirement {requirement_id!r}"
        record_refs = requirement.get("recordIds")
        if not isinstance(record_refs, list) or not record_refs:
            errors.append(f"{owner}: recordIds must contain at least one record")
            continue
        for duplicate in sorted(_duplicates(record_refs)):
            errors.append(f"{owner}: duplicate record reference: {duplicate}")
        for record_id in record_refs:
            if record_id not in records_by_id:
                errors.append(f"{owner}: unknown implementation-evidence record {record_id}")
    return errors


def release_readiness_errors(evidence: dict[str, Any]) -> list[str]:
    """Return completion blockers for the artifact-neutral release evidence graph."""

    errors: list[str] = []
    if evidence.get("mode") != "product":
        return ["release readiness requires product implementation evidence"]

    requirements = evidence.get("requirements", [])
    records = evidence.get("records", [])
    commands = evidence.get("commands", [])
    gates = evidence.get("releaseGates", [])
    if not isinstance(requirements, list) or not requirements:
        errors.append("release readiness requires at least one explicit product requirement")
    if not isinstance(records, list) or not records:
        errors.append("release readiness requires at least one implementation-evidence record")
        return errors
    if not isinstance(commands, list) or not commands:
        errors.append("release readiness requires at least one authoritative command")
    if not isinstance(gates, list) or not gates:
        errors.append("release readiness requires at least one release gate")

    records_by_id = {
        record.get("id"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }

    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        owner = f"record {record_id}"
        boundary = record.get("implementationBoundary")
        if not isinstance(boundary, dict) or boundary.get("status") != "verified":
            errors.append(f"{owner}: implementation boundary is not verified")
        elif not boundary.get("locator"):
            errors.append(f"{owner}: verified implementation boundary requires locator")

        gate_refs = record.get("releaseGateIds")
        if not isinstance(gate_refs, list) or not gate_refs:
            errors.append(f"{owner}: release readiness requires at least one release gate")

        for field, label in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            proofs = record.get(field)
            if not isinstance(proofs, list) or not proofs:
                errors.append(f"{owner}: release readiness requires {label} evidence")
                continue
            for proof in proofs:
                if not isinstance(proof, dict):
                    continue
                proof_id = proof.get("id")
                status = proof.get("status")
                if status != "verified":
                    detail = ""
                    if status == "deferred" and proof.get("deferredReason"):
                        detail = f" ({proof.get('deferredReason')})"
                    errors.append(
                        f"{owner} proof {proof_id}: {label} evidence is {status}, not verified{detail}"
                    )
                    continue
                for required in ("kind", "executionClass", "locator", "commandId", "expectedResult"):
                    if not proof.get(required):
                        errors.append(
                            f"{owner} proof {proof_id}: verified evidence requires {required}"
                        )

    if isinstance(requirements, list):
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            requirement_id = requirement.get("id")
            for record_id in requirement.get("recordIds", []):
                if record_id not in records_by_id:
                    errors.append(
                        f"requirement {requirement_id!r}: release readiness cannot resolve record {record_id}"
                    )
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(root)
        evidence = load_json(root / "contracts/implementation-evidence.json")
    except Exception as exc:
        return [f"cannot load implementation evidence: {exc}"]
    if not isinstance(evidence, dict):
        return ["implementation evidence must be an object"]

    requirements = evidence.get("requirements", [])
    commands = evidence.get("commands", [])
    gates = evidence.get("releaseGates", [])
    records = evidence.get("records", [])
    mode = evidence.get("mode")
    if not all(isinstance(value, list) for value in (requirements, commands, gates, records)):
        return ["implementation evidence collections must be arrays"]

    command_ids = [entry.get("id") for entry in commands if isinstance(entry, dict)]
    gate_ids = [entry.get("id") for entry in gates if isinstance(entry, dict)]
    record_ids = [entry.get("id") for entry in records if isinstance(entry, dict)]
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
        if not isinstance(gate, dict):
            continue
        refs = set(gate.get("commandIds", []))
        gate_commands[gate.get("id")] = refs
        for missing in sorted(refs - known_commands):
            errors.append(f"release gate {gate.get('id')}: unknown command {missing}")

    if mode == "template":
        if requirements or commands or gates or records:
            errors.append("template implementation evidence must be empty")
        return errors
    if mode != "product":
        return [f"unsupported implementation-evidence mode: {mode!r}"]

    errors.extend(requirement_traceability_errors(evidence))

    for record in records:
        if not isinstance(record, dict):
            continue
        owner = f"record {record.get('id')}"
        target = record.get("target", {})
        if not isinstance(target, dict):
            errors.append(f"{owner}: target must be an object")
            continue
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
                errors.append(f"{owner}: unknown contract transition {contract_id} {pair}")

        gate_refs = set(record.get("releaseGateIds", []))
        used_gates.update(gate_refs)
        for missing in sorted(gate_refs - known_gates):
            errors.append(f"{owner}: unknown release gate {missing}")

        record_commands: set[Any] = set()
        proofs = list(record.get("positiveEvidence", [])) + list(record.get("negativeEvidence", []))
        for proof in proofs:
            if not isinstance(proof, dict):
                continue
            proof_ids.append(proof.get("id"))
            command_id = proof.get("commandId")
            if command_id:
                used_commands.add(command_id)
                record_commands.add(command_id)
                if command_id not in known_commands:
                    errors.append(f"{owner} proof {proof.get('id')}: unknown command {command_id}")

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="also fail unless every mandatory product boundary/proof is release-ready",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = validate(root)
    evidence: dict[str, Any] | None = None
    if not errors:
        loaded = load_json(root / "contracts/implementation-evidence.json")
        if isinstance(loaded, dict):
            evidence = loaded
            if args.require_ready:
                errors.extend(release_readiness_errors(loaded))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if evidence is not None and evidence.get("mode") == "product":
        records = evidence.get("records", [])
        if isinstance(records, list):
            for warning in proof_reuse_warnings(records):
                print(f"WARNING: {warning}")
    if args.require_ready:
        print("Implementation evidence release readiness: READY")
    else:
        print("Implementation evidence structural validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
