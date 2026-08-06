#!/usr/bin/env python3
"""Validate implementation-evidence coverage and repository-local references."""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path
from typing import Any, Hashable

try:
    from scripts import validate_contracts
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    import validate_contracts  # type: ignore[no-redef]

def _unresolved_absolute(path: str | Path) -> Path:
    """Return an absolute path without resolving symbolic links."""

    return Path(os.path.abspath(os.fspath(path)))


def _invocation_root() -> Path:
    """Preserve a symlinked CLI invocation path for root preflight."""

    file_root = _unresolved_absolute(__file__).parents[1]
    pwd_value = os.environ.get("PWD")
    if not pwd_value:
        return file_root

    pwd = Path(pwd_value)
    if not pwd.is_absolute():
        return file_root

    candidate = pwd / "scripts" / Path(__file__).name
    try:
        if candidate.exists() and os.path.samefile(candidate, __file__):
            return pwd
    except OSError:
        pass
    return file_root


def _root_symlink_error(root: Path) -> str | None:
    """Reject a symbolic link at any component of the unresolved root path."""

    absolute = _unresolved_absolute(root)
    candidate = Path(absolute.anchor) if absolute.anchor else Path()
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts

    for part in parts:
        candidate /= part
        try:
            is_symlink = candidate.is_symlink()
        except (OSError, ValueError) as exc:
            return f"repository root path cannot be inspected safely: {exc}"
        if not is_symlink:
            continue
        if candidate == absolute:
            return "repository root must not be a symbolic link"
        return "repository root path must not contain symbolic links"
    return None


ROOT = _invocation_root()
EVIDENCE_CONTRACT_ID = "implementation_evidence"


def _has_visible_character(value: str) -> bool:
    return any(
        character not in validate_contracts.VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def _duplicate_values(values: list[Hashable]) -> set[Hashable]:
    seen: set[Hashable] = set()
    duplicates: set[Hashable] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _target_key(target: dict[str, Any]) -> tuple[Hashable, ...]:
    kind = target["kind"]
    if kind == "contract-transition":
        return (
            kind,
            target["contractId"],
            target["fromVersion"],
            target["toVersion"],
        )
    return (kind, target["id"])


def _render_target(key: tuple[Hashable, ...]) -> str:
    if key[0] == "contract-transition":
        return f"{key[1]} version {key[2]} to {key[3]}"
    return f"{key[0]} {key[1]}"


def _expected_targets(
    manifest: dict[str, Any],
    documents: dict[str, Any],
) -> set[tuple[Hashable, ...]]:
    targets: set[tuple[Hashable, ...]] = set()

    for surface in documents["surfaces"]["surfaces"]:
        targets.add(("surface", surface["id"]))
    for route in documents["routes"]["routes"]:
        targets.add(("route", route["id"]))
    for state in documents["ui_states"]["states"]:
        targets.add(("ui-state", state["id"]))
    for viewport in documents["viewports"]["viewports"]:
        targets.add(("viewport", viewport["id"]))
    for capability in documents["viewports"]["inputCapabilities"]:
        targets.add(("input-capability", capability))

    histories: list[tuple[str, list[dict[str, Any]]]] = [
        ("contract-manifest", manifest["versionHistory"])
    ]
    histories.extend(
        (entry["id"], entry["versionHistory"])
        for entry in manifest["contracts"]
    )
    histories.extend(
        (entry["id"], entry["versionHistory"])
        for entry in manifest["retiredContracts"]
    )
    for contract_id, history in histories:
        for transition in history[1:]:
            version = transition["version"]
            targets.add(
                ("contract-transition", contract_id, version - 1, version)
            )
    return targets


def _negative_evidence_required_targets(
    manifest: dict[str, Any],
    documents: dict[str, Any],
) -> set[tuple[Hashable, ...]]:
    required: set[tuple[Hashable, ...]] = set()

    for surface in documents["surfaces"]["surfaces"]:
        authorization_mode = surface["authorization"]["mode"]
        if surface["authentication"] == "required" or authorization_mode != "public":
            required.add(("surface", surface["id"]))

    for route in documents["routes"]["routes"]:
        failures = route["accessFailures"]
        if route["authentication"] == "required" or any(
            behavior != "not-applicable" for behavior in failures.values()
        ):
            required.add(("route", route["id"]))

    for state in documents["ui_states"]["states"]:
        if state["category"] in {"degraded", "error", "connectivity", "access"}:
            required.add(("ui-state", state["id"]))

    histories: list[tuple[str, list[dict[str, Any]]]] = [
        ("contract-manifest", manifest["versionHistory"])
    ]
    histories.extend(
        (entry["id"], entry["versionHistory"])
        for entry in manifest["contracts"]
    )
    histories.extend(
        (entry["id"], entry["versionHistory"])
        for entry in manifest["retiredContracts"]
    )
    for contract_id, history in histories:
        for transition in history[1:]:
            if transition["changeType"] == "breaking":
                version = transition["version"]
                required.add(
                    ("contract-transition", contract_id, version - 1, version)
                )
    return required


def _validate_visible_text(
    value: Any,
    *,
    owner: str,
    field: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or not _has_visible_character(value):
        errors.append(f"{owner}: {field} must contain visible text")


def validate_evidence_documents(
    manifest: dict[str, Any],
    documents: dict[str, Any],
) -> list[str]:
    """Validate cross-contract coverage and product evidence requirements."""

    errors: list[str] = []
    evidence = documents.get(EVIDENCE_CONTRACT_ID)
    if not isinstance(evidence, dict):
        return [
            "implementation evidence: active contract document is missing or malformed"
        ]

    try:
        mode = evidence["mode"]
        commands = evidence["commands"]
        release_gates = evidence["releaseGates"]
        records = evidence["records"]
        expected_targets = _expected_targets(manifest, documents)
        negative_required = _negative_evidence_required_targets(
            manifest, documents
        )
    except (KeyError, TypeError, AttributeError) as exc:
        return [f"implementation evidence: metadata is incomplete or malformed: {exc}"]

    command_ids = [command["id"] for command in commands]
    gate_ids = [gate["id"] for gate in release_gates]
    record_ids = [record["id"] for record in records]

    for duplicate in sorted(_duplicate_values(command_ids)):
        errors.append(f"duplicate implementation evidence command id: {duplicate}")
    for duplicate in sorted(_duplicate_values(gate_ids)):
        errors.append(f"duplicate implementation evidence release gate id: {duplicate}")
    for duplicate in sorted(_duplicate_values(record_ids)):
        errors.append(f"duplicate implementation evidence record id: {duplicate}")

    known_commands = set(command_ids)
    known_gates = set(gate_ids)

    for command in commands:
        owner = f"implementation evidence command {command['id']}"
        _validate_visible_text(
            command.get("command"), owner=owner, field="command", errors=errors
        )
        _validate_visible_text(
            command.get("purpose"), owner=owner, field="purpose", errors=errors
        )

    gate_commands_by_id: dict[str, set[str]] = {}
    for gate in release_gates:
        owner = f"implementation evidence release gate {gate['id']}"
        _validate_visible_text(
            gate.get("purpose"), owner=owner, field="purpose", errors=errors
        )
        command_refs = set(gate["commandIds"])
        gate_commands_by_id[gate["id"]] = command_refs
        for command_id in sorted(command_refs - known_commands):
            errors.append(
                f"{owner}: unknown command reference {command_id}"
            )

    target_keys = [_target_key(record["target"]) for record in records]
    for duplicate in sorted(
        _duplicate_values(target_keys), key=lambda item: tuple(map(str, item))
    ):
        errors.append(
            f"duplicate implementation evidence target: {_render_target(duplicate)}"
        )

    actual_targets = set(target_keys)
    for target in sorted(
        expected_targets - actual_targets, key=lambda item: tuple(map(str, item))
    ):
        errors.append(
            f"missing implementation evidence target: {_render_target(target)}"
        )
    for target in sorted(
        actual_targets - expected_targets, key=lambda item: tuple(map(str, item))
    ):
        errors.append(
            f"unknown implementation evidence target: {_render_target(target)}"
        )

    proof_ids: list[str] = []
    referenced_commands: set[str] = set()
    referenced_gates: set[str] = set()

    for record, target_key in zip(records, target_keys):
        owner = f"implementation evidence record {record['id']}"
        boundary = record["implementationBoundary"]
        _validate_visible_text(
            boundary.get("description"),
            owner=owner,
            field="implementationBoundary.description",
            errors=errors,
        )

        proofs = record["positiveEvidence"] + record["negativeEvidence"]
        proof_ids.extend(proof["id"] for proof in proofs)
        for proof in proofs:
            proof_owner = f"{owner} proof {proof['id']}"
            _validate_visible_text(
                proof.get("description"),
                owner=proof_owner,
                field="description",
                errors=errors,
            )
            command_id = proof.get("commandId")
            if command_id is not None:
                referenced_commands.add(command_id)
                if command_id not in known_commands:
                    errors.append(
                        f"{proof_owner}: unknown command reference {command_id}"
                    )

        gate_refs = set(record["releaseGateIds"])
        referenced_gates.update(gate_refs)
        for gate_id in sorted(gate_refs - known_gates):
            errors.append(f"{owner}: unknown release gate reference {gate_id}")

        if mode == "template":
            if boundary["status"] != "required":
                errors.append(
                    f"{owner}: template mode requires implementationBoundary status required"
                )
            if boundary.get("locator") is not None:
                errors.append(
                    f"{owner}: template mode must not claim an implementationBoundary locator"
                )
            for proof in proofs:
                if proof["status"] != "required":
                    errors.append(
                        f"{owner} proof {proof['id']}: template mode requires status required"
                    )
                for field in ("kind", "locator", "commandId", "expectedResult"):
                    if proof.get(field) is not None:
                        errors.append(
                            f"{owner} proof {proof['id']}: template mode must not claim {field}"
                        )
            if gate_refs:
                errors.append(
                    f"{owner}: template mode must not claim release gates"
                )

        elif mode == "product":
            if boundary["status"] != "verified":
                errors.append(
                    f"{owner}: product mode requires a verified implementation boundary"
                )
            _validate_visible_text(
                boundary.get("locator"),
                owner=owner,
                field="implementationBoundary.locator",
                errors=errors,
            )
            if not gate_refs:
                errors.append(
                    f"{owner}: product mode requires at least one release gate"
                )
            if target_key in negative_required and not record["negativeEvidence"]:
                errors.append(
                    f"{owner}: {_render_target(target_key)} requires negative evidence"
                )

            proof_command_ids: set[str] = set()
            for proof in proofs:
                proof_owner = f"{owner} proof {proof['id']}"
                if proof["status"] != "verified":
                    errors.append(
                        f"{proof_owner}: product mode requires status verified"
                    )
                for field in ("kind", "locator", "commandId", "expectedResult"):
                    if proof.get(field) is None:
                        errors.append(
                            f"{proof_owner}: product mode requires {field}"
                        )
                _validate_visible_text(
                    proof.get("locator"),
                    owner=proof_owner,
                    field="locator",
                    errors=errors,
                )
                _validate_visible_text(
                    proof.get("expectedResult"),
                    owner=proof_owner,
                    field="expectedResult",
                    errors=errors,
                )
                if proof.get("commandId") is not None:
                    proof_command_ids.add(proof["commandId"])

            gated_commands: set[str] = set()
            for gate_id in gate_refs:
                gated_commands.update(gate_commands_by_id.get(gate_id, set()))
            for command_id in sorted(proof_command_ids - gated_commands):
                errors.append(
                    f"{owner}: evidence command {command_id} is not executed by a selected release gate"
                )

    for duplicate in sorted(_duplicate_values(proof_ids)):
        errors.append(f"duplicate implementation evidence proof id: {duplicate}")

    if mode == "template":
        if commands:
            errors.append("implementation evidence: template mode requires commands to be empty")
        if release_gates:
            errors.append(
                "implementation evidence: template mode requires releaseGates to be empty"
            )
    elif mode == "product":
        if not commands:
            errors.append(
                "implementation evidence: product mode requires at least one authoritative command"
            )
        if not release_gates:
            errors.append(
                "implementation evidence: product mode requires at least one release gate"
            )
        for gate_id in sorted(known_gates - referenced_gates):
            errors.append(
                f"unused implementation evidence release gate: {gate_id}"
            )
        gate_referenced_commands = set().union(
            *(gate_commands_by_id.values() or [set()])
        )
        used_commands = referenced_commands | gate_referenced_commands
        for command_id in sorted(known_commands - used_commands):
            errors.append(f"unused implementation evidence command: {command_id}")
    else:
        errors.append(f"implementation evidence: unsupported mode {mode!r}")

    return errors


def validate_implementation_evidence(root: Path) -> list[str]:
    """Load the repository and validate implementation-evidence references."""

    root_error = _root_symlink_error(root)
    if root_error:
        return [root_error]

    structural_errors = validate_contracts.validate_repository(root)
    if structural_errors:
        return [
            "implementation evidence validation requires structurally valid active contracts",
            *structural_errors,
        ]

    try:
        manifest = validate_contracts.load_contract_manifest(root)
        documents = validate_contracts.load_contract_documents(root)
        return validate_evidence_documents(manifest, documents)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
    ) as exc:
        return [f"implementation evidence validation could not load repository metadata: {exc}"]


def main() -> int:
    errors = validate_implementation_evidence(ROOT)
    if errors:
        print("Implementation evidence validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All implementation evidence targets and release references are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
