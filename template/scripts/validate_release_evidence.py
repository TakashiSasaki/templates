#!/usr/bin/env python3
"""Validate release evidence against implementation commands and release gates."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Hashable, Sequence

try:
    from scripts import validate_contracts
    from scripts import validate_implementation_evidence
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    import validate_contracts  # type: ignore[no-redef]
    import validate_implementation_evidence  # type: ignore[no-redef]


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
RELEASE_EVIDENCE_CONTRACT_ID = "release_evidence"
_TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$"
)
TimestampValue = tuple[datetime, int]


def _has_visible_character(value: str) -> bool:
    return any(
        character not in validate_contracts.VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def _validate_visible_text(
    value: Any,
    *,
    owner: str,
    field: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or not _has_visible_character(value):
        errors.append(f"{owner}: {field} must contain visible text")


def _duplicate_values(values: list[Hashable]) -> set[Hashable]:
    seen: set[Hashable] = set()
    duplicates: set[Hashable] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _command_digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def _parse_timestamp(
    value: Any,
    *,
    owner: str,
    field: str,
    errors: list[str],
) -> TimestampValue | None:
    if not isinstance(value, str):
        errors.append(f"{owner}: {field} must be a UTC timestamp")
        return None

    match = _TIMESTAMP_PATTERN.fullmatch(value)
    if match is None:
        errors.append(f"{owner}: {field} must be a UTC timestamp")
        return None

    try:
        whole_seconds = datetime.strptime(
            match.group(1),
            "%Y-%m-%dT%H:%M:%S",
        )
    except ValueError:
        errors.append(f"{owner}: {field} must be a UTC timestamp")
        return None

    fractional_digits = match.group(2) or ""
    nanoseconds = int(fractional_digits.ljust(9, "0") or "0")
    return whole_seconds, nanoseconds


def validate_release_evidence_documents(
    manifest: dict[str, Any],
    documents: dict[str, Any],
    *,
    expected_revision: str | None = None,
) -> list[str]:
    """Validate one template requirement document or product release record."""

    del manifest
    errors: list[str] = []
    release = documents.get(RELEASE_EVIDENCE_CONTRACT_ID)
    implementation = documents.get("implementation_evidence")
    if not isinstance(release, dict):
        return ["release evidence: active contract document is missing or malformed"]
    if not isinstance(implementation, dict):
        return ["release evidence: implementation evidence is missing or malformed"]

    try:
        mode = release["mode"]
        command_results = release["commandResults"]
        gate_results = release["gateResults"]
    except (KeyError, TypeError, AttributeError) as exc:
        return [f"release evidence: metadata is incomplete or malformed: {exc}"]

    if mode == "template":
        if implementation.get("mode") != "template":
            errors.append(
                "release evidence: template mode requires template implementation evidence"
            )
        if expected_revision is not None:
            errors.append(
                "release evidence: template mode must not receive an expected revision"
            )
        for field in ("subject", "provenance", "decision"):
            if release.get(field) is not None:
                errors.append(f"release evidence: template mode must not claim {field}")
        if command_results:
            errors.append(
                "release evidence: template mode requires commandResults to be empty"
            )
        if gate_results:
            errors.append(
                "release evidence: template mode requires gateResults to be empty"
            )
        return errors

    if mode != "product":
        return [f"release evidence: unsupported mode {mode!r}"]

    if implementation.get("mode") != "product":
        errors.append(
            "release evidence: product mode requires product implementation evidence"
        )
    if expected_revision is None:
        errors.append(
            "release evidence: product mode requires an expected revision"
        )

    subject = release.get("subject")
    provenance = release.get("provenance")
    decision = release.get("decision")
    if not isinstance(subject, dict):
        errors.append("release evidence: product mode requires subject")
        subject = {}
    if not isinstance(provenance, dict):
        errors.append("release evidence: product mode requires provenance")
        provenance = {}
    if not isinstance(decision, dict):
        errors.append("release evidence: product mode requires decision")
        decision = {}

    revision = subject.get("revision")
    if expected_revision is not None and revision != expected_revision:
        errors.append(
            "release evidence subject: "
            f"revision {revision!r} does not match expected revision {expected_revision!r}"
        )
    _validate_visible_text(
        subject.get("description"),
        owner="release evidence subject",
        field="description",
        errors=errors,
    )

    for field in ("id", "locator"):
        _validate_visible_text(
            provenance.get(field),
            owner="release evidence provenance",
            field=field,
            errors=errors,
        )
    generated_at = _parse_timestamp(
        provenance.get("generatedAt"),
        owner="release evidence provenance",
        field="generatedAt",
        errors=errors,
    )

    _validate_visible_text(
        decision.get("description"),
        owner="release evidence decision",
        field="description",
        errors=errors,
    )
    decided_at = _parse_timestamp(
        decision.get("decidedAt"),
        owner="release evidence decision",
        field="decidedAt",
        errors=errors,
    )
    if decision.get("status") != "approved":
        errors.append(
            "release evidence decision: release status must be approved"
        )

    commands = implementation.get("commands", [])
    release_gates = implementation.get("releaseGates", [])
    known_commands = {
        command["id"]: command
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("id"), str)
    }
    known_gates = {
        gate["id"]: gate
        for gate in release_gates
        if isinstance(gate, dict) and isinstance(gate.get("id"), str)
    }
    expected_command_ids: set[str] = set()
    for gate in known_gates.values():
        command_ids = gate.get("commandIds", [])
        if isinstance(command_ids, list):
            expected_command_ids.update(
                command_id
                for command_id in command_ids
                if isinstance(command_id, str)
            )

    command_result_ids = [
        result.get("commandId")
        for result in command_results
        if isinstance(result, dict)
    ]
    for duplicate in sorted(
        value for value in _duplicate_values(command_result_ids)
        if isinstance(value, str)
    ):
        errors.append(f"duplicate release evidence command result: {duplicate}")

    actual_command_ids = {
        value for value in command_result_ids if isinstance(value, str)
    }
    for command_id in sorted(expected_command_ids - actual_command_ids):
        errors.append(f"missing release evidence command result: {command_id}")
    for command_id in sorted(actual_command_ids - set(known_commands)):
        errors.append(f"unknown release evidence command result: {command_id}")

    command_statuses: dict[str, str] = {}
    completion_times: list[TimestampValue] = []
    for result in command_results:
        if not isinstance(result, dict):
            continue
        command_id = result.get("commandId")
        owner = f"release evidence command result {command_id}"
        if not isinstance(command_id, str):
            continue
        command_statuses[command_id] = result.get("status")
        command = known_commands.get(command_id)
        if command is not None:
            command_text = command.get("command")
            if isinstance(command_text, str):
                try:
                    expected_digest = _command_digest(command_text)
                except UnicodeEncodeError:
                    errors.append(
                        f"release evidence command {command_id}: "
                        "authoritative command must be UTF-8 encodable"
                    )
                else:
                    if result.get("commandDigest") != expected_digest:
                        errors.append(
                            f"{owner}: commandDigest does not match the authoritative command"
                        )
            else:
                errors.append(
                    f"release evidence command {command_id}: "
                    "authoritative command must be text"
                )
        if result.get("status") != "passed":
            errors.append(f"{owner}: status must be passed")
        if result.get("exitCode") != 0:
            errors.append(f"{owner}: exitCode must be 0")
        _validate_visible_text(
            result.get("resultLocator"),
            owner=owner,
            field="resultLocator",
            errors=errors,
        )
        started_at = _parse_timestamp(
            result.get("startedAt"),
            owner=owner,
            field="startedAt",
            errors=errors,
        )
        completed_at = _parse_timestamp(
            result.get("completedAt"),
            owner=owner,
            field="completedAt",
            errors=errors,
        )
        if started_at is not None and completed_at is not None:
            if completed_at < started_at:
                errors.append(f"{owner}: completedAt must not precede startedAt")
            completion_times.append(completed_at)

    gate_result_ids = [
        result.get("gateId") for result in gate_results if isinstance(result, dict)
    ]
    for duplicate in sorted(
        value for value in _duplicate_values(gate_result_ids)
        if isinstance(value, str)
    ):
        errors.append(f"duplicate release evidence gate result: {duplicate}")

    actual_gate_ids = {
        value for value in gate_result_ids if isinstance(value, str)
    }
    for gate_id in sorted(set(known_gates) - actual_gate_ids):
        errors.append(f"missing release evidence gate result: {gate_id}")
    for gate_id in sorted(actual_gate_ids - set(known_gates)):
        errors.append(f"unknown release evidence gate result: {gate_id}")

    for result in gate_results:
        if not isinstance(result, dict):
            continue
        gate_id = result.get("gateId")
        owner = f"release evidence gate result {gate_id}"
        if not isinstance(gate_id, str):
            continue
        _validate_visible_text(
            result.get("resultLocator"),
            owner=owner,
            field="resultLocator",
            errors=errors,
        )
        if result.get("status") != "passed":
            errors.append(f"{owner}: status must be passed")
        gate = known_gates.get(gate_id)
        if gate is not None:
            failed_commands = sorted(
                command_id
                for command_id in gate["commandIds"]
                if command_statuses.get(command_id) != "passed"
            )
            for command_id in failed_commands:
                errors.append(
                    f"{owner}: command {command_id} did not pass"
                )

    if completion_times and decided_at is not None:
        latest_completion = max(completion_times)
        if decided_at < latest_completion:
            errors.append(
                "release evidence decision: decidedAt must not precede command completion"
            )
    if decided_at is not None and generated_at is not None:
        if generated_at < decided_at:
            errors.append(
                "release evidence provenance: generatedAt must not precede decidedAt"
            )

    return errors


def validate_release_evidence(
    root: Path,
    *,
    expected_revision: str | None = None,
) -> list[str]:
    """Load the repository and validate release evidence and prerequisites."""

    root_error = _root_symlink_error(root)
    if root_error:
        return [root_error]

    structural_errors = validate_contracts.validate_repository(root)
    if structural_errors:
        return structural_errors

    try:
        manifest = validate_contracts.load_contract_manifest(root)
        documents = validate_contracts.load_contract_documents(root)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        return [f"release evidence: repository metadata cannot be loaded: {exc}"]

    implementation_errors = (
        validate_implementation_evidence.validate_evidence_documents(
            manifest,
            documents,
        )
    )
    if implementation_errors:
        return implementation_errors

    return validate_release_evidence_documents(
        manifest,
        documents,
        expected_revision=expected_revision,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate release evidence for one exact product revision."
    )
    parser.add_argument(
        "--expected-revision",
        help="Exact lowercase 40-hex Git revision represented by product evidence.",
    )
    arguments = parser.parse_args(argv)

    errors = validate_release_evidence(
        ROOT,
        expected_revision=arguments.expected_revision,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("All release evidence and revision bindings are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
