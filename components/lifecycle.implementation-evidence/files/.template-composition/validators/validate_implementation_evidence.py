#!/usr/bin/env python3
"""Validate generic implementation-evidence semantics after schema validation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from contract_common import contract_entries, load_json, load_manifest


REUSE_FAMILY_THRESHOLD = 3
PROOF_KIND_CAPABILITY = {
    "unit-test": "unit",
    "integration-test": "integration",
    "end-to-end-test": "end-to-end",
    "accessibility-test": "accessibility",
    "migration-test": "migration",
    "inspection": "inspection",
    "other": "other",
}
_DRIVE_PREFIX_PATTERN = re.compile(r"^[A-Za-z]:")
_REPOSITORY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_PYTHON_MODULE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_repository_locator(value: str) -> bool:
    """Mirror repositoryLocator schema safety for direct semantic callers."""

    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or _DRIVE_PREFIX_PATTERN.match(value)
    ):
        return False
    parts = value.split("/")
    return bool(parts) and all(
        part not in {"", ".", ".."}
        and part.lower() != ".git"
        and _REPOSITORY_SEGMENT_PATTERN.fullmatch(part) is not None
        for part in parts
    )


def _python_module_from_locator(locator: str) -> str | None:
    if not locator.endswith(".py"):
        return None
    parts = locator[:-3].split("/")
    if not parts or not all(_PYTHON_MODULE_SEGMENT_PATTERN.fullmatch(part) for part in parts):
        return None
    return ".".join(parts)


def infer_harness_invocation(command_text: object, locator: str) -> str | None:
    """Infer a supported invocation only from an exact command/harness match."""

    if command_text == f"python {locator}":
        return "python-script"
    module = _python_module_from_locator(locator)
    if module is not None and command_text == f"python -m unittest {module}":
        return "python-unittest"
    if command_text == f"./{locator}":
        return "direct"
    return None


def _duplicates(values: list[Any]) -> set[Any]:
    seen: set[Any] = set()
    out: set[Any] = set()
    for value in values:
        if value in seen:
            out.add(value)
        seen.add(value)
    return out


def _target_signature(target: object) -> tuple[Any, ...]:
    if not isinstance(target, dict):
        return ("invalid", repr(target))
    kind = target.get("kind")
    if kind == "contract-item":
        return (
            "contract-item",
            target.get("contractId"),
            target.get("itemKind"),
            target.get("itemId"),
        )
    if kind == "contract-transition":
        return (
            "contract-transition",
            target.get("contractId"),
            target.get("fromVersion"),
            target.get("toVersion"),
        )
    return (kind, target.get("contractId"))


def _target_text(signature: tuple[Any, ...]) -> str:
    return "/".join(str(value) for value in signature)


def _target_contract_errors(
    target: object,
    known_contracts: dict[str, Any],
    owner: str,
) -> list[str]:
    if not isinstance(target, dict):
        return [f"{owner}: target must be an object"]
    contract_id = target.get("contractId")
    if contract_id not in known_contracts:
        return [f"{owner}: unknown contract target {contract_id}"]
    if target.get("kind") != "contract-transition":
        return []
    transitions = {
        (entry["version"] - 1, entry["version"])
        for entry in known_contracts[contract_id]["versionHistory"][1:]
    }
    pair = (target.get("fromVersion"), target.get("toVersion"))
    if pair not in transitions:
        return [f"{owner}: unknown contract transition {contract_id} {pair}"]
    return []


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


def _command_index(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    commands = evidence.get("commands", [])
    if not isinstance(commands, list):
        return {}
    return {
        command.get("id"): command
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("id"), str)
    }


def command_capabilities(command: object) -> set[str]:
    if not isinstance(command, dict):
        return set()
    execution = command.get("execution")
    if not isinstance(execution, dict):
        return set()
    capabilities = execution.get("capabilities")
    if not isinstance(capabilities, list):
        return set()
    return {item for item in capabilities if isinstance(item, str)}


def proof_execution_errors(
    evidence: dict[str, Any], root: Path | None = None
) -> list[str]:
    """Bind proof-kind claims to authoritative command capabilities and harnesses."""

    if evidence.get("mode") != "product":
        return []
    commands = _command_index(evidence)
    errors: list[str] = []

    for command_id, command in commands.items():
        execution = command.get("execution")
        if not isinstance(execution, dict):
            errors.append(
                f"implementation command {command_id}: execution profile is required"
            )
            continue
        capabilities = command_capabilities(command)
        if not capabilities:
            errors.append(
                f"implementation command {command_id}: execution capabilities must be non-empty"
            )
        harness = execution.get("harness")
        if not isinstance(harness, dict):
            errors.append(
                f"implementation command {command_id}: execution harness is required"
            )
        else:
            if harness.get("kind") != "repository-file":
                errors.append(
                    f"implementation command {command_id}: execution harness kind must be 'repository-file'"
                )
            locator = harness.get("locator")
            locator_valid = isinstance(locator, str) and bool(locator)
            if not locator_valid:
                errors.append(
                    f"implementation command {command_id}: execution harness locator is required"
                )
            elif not _safe_repository_locator(locator):
                errors.append(
                    f"implementation command {command_id}: execution harness locator must be a safe repository-relative file path: {locator}"
                )
                locator_valid = False
            if locator_valid:
                assert isinstance(locator, str)
                invocation = infer_harness_invocation(command.get("command"), locator)
                if invocation is None:
                    errors.append(
                        f"implementation command {command_id}: command must exactly invoke declared harness {locator!r} "
                        "as 'python <path>', 'python -m unittest <module>', or './<path>'"
                    )
            if locator_valid and root is not None:
                assert isinstance(locator, str)
                candidate = root / locator
                if candidate.is_symlink():
                    errors.append(
                        f"implementation command {command_id}: execution harness must be a regular non-symlink file: {locator}"
                    )
                elif not candidate.is_file():
                    errors.append(
                        f"implementation command {command_id}: execution harness does not exist: {locator}"
                    )
        if not isinstance(execution.get("supportsNegativePath"), bool):
            errors.append(
                f"implementation command {command_id}: supportsNegativePath must be boolean"
            )

    records = evidence.get("records", [])
    if not isinstance(records, list):
        return errors
    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        for field, polarity in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            proofs = record.get(field, [])
            if not isinstance(proofs, list):
                continue
            for proof in proofs:
                if not isinstance(proof, dict):
                    continue
                proof_id = proof.get("id")
                command_id = proof.get("commandId")
                command = commands.get(command_id) if isinstance(command_id, str) else None
                if command is None:
                    continue
                kind = proof.get("kind")
                required_capability = PROOF_KIND_CAPABILITY.get(kind)
                if required_capability is not None and required_capability not in command_capabilities(command):
                    errors.append(
                        f"record {record_id} {polarity} proof {proof_id}: proof kind {kind!r} "
                        f"requires command capability {required_capability!r} on {command_id!r}"
                    )
                if polarity == "negative":
                    execution = command.get("execution")
                    supports_negative = (
                        execution.get("supportsNegativePath")
                        if isinstance(execution, dict)
                        else None
                    )
                    if supports_negative is not True:
                        errors.append(
                            f"record {record_id} negative proof {proof_id}: command {command_id!r} "
                            "must declare supportsNegativePath=true"
                        )
    return errors


def proof_reuse_warnings(records: list[dict[str, Any]]) -> list[str]:
    """Return non-fatal diagnostics for suspiciously broad exact proof reuse."""

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


def requirement_traceability_errors(
    evidence: dict[str, Any],
    known_contracts: dict[str, Any] | None = None,
) -> list[str]:
    """Validate stable requirement intent, targets, and product record edges."""

    mode = evidence.get("mode")
    requirements = evidence.get("requirements")
    if requirements is None:
        if mode in {"planning", "product"}:
            return [f"{mode} implementation-evidence requires a non-empty requirements ledger"]
        return []
    if not isinstance(requirements, list):
        return ["implementation-evidence requirements must be an array"]
    if mode in {"planning", "product"} and not requirements:
        return [f"{mode} implementation-evidence requires a non-empty requirements ledger"]

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
        required_kinds = requirement.get("requiredPositiveProofKinds")
        if not isinstance(required_kinds, list) or not required_kinds:
            errors.append(
                f"{owner}: requiredPositiveProofKinds must contain at least one proof kind"
            )
            required_kinds = []

        targets = requirement.get("targets")
        if mode == "planning":
            if not isinstance(targets, list) or not targets:
                errors.append(
                    f"{owner}: planning targets must contain at least one contract target"
                )
                targets = []
        elif targets is None:
            targets = []
        elif not isinstance(targets, list) or not targets:
            errors.append(
                f"{owner}: product targets, when present, must contain at least one contract target"
            )
            targets = []
        target_signatures = [_target_signature(target) for target in targets]
        for duplicate in sorted(_duplicates(target_signatures), key=str):
            errors.append(f"{owner}: duplicate target: {_target_text(duplicate)}")
        if known_contracts is not None:
            for target_index, target in enumerate(targets):
                errors.extend(
                    _target_contract_errors(
                        target,
                        known_contracts,
                        f"{owner} target {target_index}",
                    )
                )

        record_refs = requirement.get("recordIds")
        if not isinstance(record_refs, list):
            errors.append(f"{owner}: recordIds must be an array")
            continue
        if mode == "planning":
            if record_refs:
                errors.append(
                    f"{owner}: planning requirement recordIds must stay empty until product implementation records exist"
                )
            continue
        if not record_refs:
            errors.append(f"{owner}: recordIds must contain at least one record")
            continue
        for duplicate in sorted(_duplicates(record_refs)):
            errors.append(f"{owner}: duplicate record reference: {duplicate}")

        linked_target_signatures: list[tuple[Any, ...]] = []
        all_records_known = True
        for record_id in record_refs:
            record = records_by_id.get(record_id)
            if record is None:
                all_records_known = False
                errors.append(f"{owner}: unknown implementation-evidence record {record_id}")
                continue
            linked_target_signatures.append(_target_signature(record.get("target")))
            positive = record.get("positiveEvidence")
            if not isinstance(positive, list) or not any(
                isinstance(proof, dict)
                and proof.get("status") in {"verified", "deferred"}
                for proof in positive
            ):
                errors.append(
                    f"{owner}: linked record {record_id} has no traceable positive evidence"
                )
            if required_kinds:
                if not isinstance(positive, list) or not any(
                    isinstance(proof, dict)
                    and proof.get("kind") in required_kinds
                    for proof in positive
                ):
                    errors.append(
                        f"{owner}: linked record {record_id} has no positive proof "
                        f"with a required kind ({', '.join(sorted(required_kinds))})"
                    )
            gates = record.get("releaseGateIds")
            if not isinstance(gates, list) or not gates:
                errors.append(
                    f"{owner}: linked record {record_id} has no release gate"
                )

        if all_records_known and targets:
            declared = set(target_signatures)
            linked = set(linked_target_signatures)
            for missing in sorted(declared - linked, key=str):
                errors.append(
                    f"{owner}: declared target {_target_text(missing)} has no linked implementation record"
                )
            for extra in sorted(linked - declared, key=str):
                errors.append(
                    f"{owner}: linked implementation record targets undeclared requirement target {_target_text(extra)}"
                )
    return errors


def release_readiness_errors(
    evidence: Any, root: Path | None = None
) -> list[str]:
    """Return blockers that prevent approved release evidence."""

    if not isinstance(evidence, dict):
        return ["release readiness blocked: implementation evidence must be an object"]

    mode = evidence.get("mode")
    if mode != "product":
        return [
            "release readiness blocked: implementation-evidence mode "
            f"{mode!r} is not 'product'"
        ]

    if root is None:
        errors = requirement_traceability_errors(evidence)
        errors.extend(proof_execution_errors(evidence, root))
    else:
        try:
            manifest = load_manifest(root)
        except Exception as exc:
            errors = [f"cannot load implementation-evidence contract manifest: {exc}"]
        else:
            errors = implementation_evidence_errors(root, manifest, evidence)
    records = evidence.get("records", [])
    if not isinstance(records, list):
        return errors + ["implementation-evidence records must be an array"]

    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        boundary = record.get("implementationBoundary")
        if not isinstance(boundary, dict) or boundary.get("status") != "verified":
            errors.append(
                f"release readiness blocked: record {record_id} implementation boundary "
                f"is {boundary.get('status') if isinstance(boundary, dict) else 'missing'}"
            )
        for field in ("positiveEvidence", "negativeEvidence"):
            proofs = record.get(field, [])
            if not isinstance(proofs, list):
                errors.append(
                    f"release readiness blocked: record {record_id} {field} is not an array"
                )
                continue
            for proof in proofs:
                if not isinstance(proof, dict):
                    continue
                status = proof.get("status")
                if status != "verified":
                    suffix = (
                        " (environment unavailable; provide the proof or explicitly "
                        "resolve the release blocker)"
                        if status == "deferred"
                        else ""
                    )
                    errors.append(
                        f"release readiness blocked: record {record_id} {field} proof "
                        f"{proof.get('id')} is {status!r}, not verified{suffix}"
                    )
    return errors


def implementation_evidence_errors(
    root: Path,
    manifest: dict[str, Any],
    evidence: Any,
) -> list[str]:
    """Validate one already-loaded implementation-evidence document."""

    if not isinstance(evidence, dict):
        return ["implementation evidence must be an object"]

    commands = evidence.get("commands", [])
    gates = evidence.get("releaseGates", [])
    records = evidence.get("records", [])
    requirements = evidence.get("requirements", [])
    mode = evidence.get("mode")
    command_ids = [
        entry.get("id")
        for entry in commands
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    gate_ids = [
        entry.get("id")
        for entry in gates
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    record_ids = [
        entry.get("id")
        for entry in records
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
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
        if commands or gates or records or requirements:
            errors.append("template implementation evidence must be empty")
        return errors
    if mode == "planning":
        if commands or gates or records:
            errors.append(
                "planning implementation evidence may contain only the requirement ledger"
            )
        errors.extend(requirement_traceability_errors(evidence, known_contracts))
        return errors
    if mode != "product":
        return [f"unsupported implementation-evidence mode: {mode!r}"]

    errors.extend(requirement_traceability_errors(evidence, known_contracts))
    errors.extend(proof_execution_errors(evidence, root))

    for record in records:
        if not isinstance(record, dict):
            continue
        owner = f"record {record.get('id')}"
        target = record.get("target", {})
        errors.extend(_target_contract_errors(target, known_contracts, owner))

        gate_refs = set(record.get("releaseGateIds", []))
        used_gates.update(gate_refs)
        for missing in sorted(gate_refs - known_gates):
            errors.append(f"{owner}: unknown release gate {missing}")

        record_commands: set[Any] = set()
        proofs = list(record.get("positiveEvidence", [])) + list(
            record.get("negativeEvidence", [])
        )
        proof_ids.extend(
            proof.get("id") for proof in proofs if isinstance(proof, dict)
        )
        for proof in proofs:
            if not isinstance(proof, dict):
                continue
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

def validate(root: Path) -> list[str]:
    try:
        manifest = load_manifest(root)
        evidence = load_json(root / "contracts/implementation-evidence.json")
    except Exception as exc:
        return [f"cannot load implementation evidence: {exc}"]
    return implementation_evidence_errors(root, manifest, evidence)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument(
        "--release-readiness",
        action="store_true",
        help="apply the stricter gate that rejects required or deferred proofs",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="render the release-readiness result for humans or machines",
    )
    args = parser.parse_args()
    if args.output_format == "json" and not args.release_readiness:
        parser.error("--format json requires --release-readiness")
    root = Path(args.root).resolve()
    evidence_path = root / "contracts/implementation-evidence.json"
    if args.release_readiness:
        try:
            evidence = load_json(evidence_path)
        except (OSError, UnicodeError, ValueError) as exc:
            evidence = None
            errors = [f"cannot load implementation evidence: {exc}"]
        else:
            errors = release_readiness_errors(evidence, root)
    else:
        errors = validate(root)
        try:
            evidence = load_json(evidence_path)
        except (OSError, UnicodeError, ValueError):
            evidence = None
    records = evidence.get("records", []) if isinstance(evidence, dict) else []
    if not isinstance(records, list):
        records = []
    warnings = (
        list(dict.fromkeys(proof_reuse_warnings(records)))
        if isinstance(evidence, dict) and evidence.get("mode") == "product"
        else []
    )

    if args.release_readiness and args.output_format == "json":
        deferred_proofs = sorted({
            proof.get("id")
            for record in records
            if isinstance(record, dict)
            for field in ("positiveEvidence", "negativeEvidence")
            for proof in record.get(field, [])
            if isinstance(proof, dict)
            and proof.get("status") == "deferred"
            and isinstance(proof.get("id"), str)
        })
        errors = list(dict.fromkeys(errors))
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "release_readiness": "not-ready" if errors else "ready",
                    "blocking_conditions": errors,
                    "deferred_proofs": deferred_proofs,
                    "warnings": warnings,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1 if errors else 0

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARNING: {warning}")
    if not args.release_readiness and isinstance(evidence, dict):
        if evidence.get("mode") == "planning":
            print(
                "Release readiness: NOT READY "
                "(planning requirement ledger is target-bound but not yet linked to implementation evidence)"
            )
        deferred = [
            proof.get("id")
            for record in evidence.get("records", [])
            if isinstance(record, dict)
            for field in ("positiveEvidence", "negativeEvidence")
            for proof in record.get(field, [])
            if isinstance(proof, dict) and proof.get("status") == "deferred"
        ]
        if deferred:
            print(
                "Release readiness: NOT READY "
                f"(deferred evidence: {', '.join(sorted(deferred))})"
            )
    print("Implementation evidence validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
