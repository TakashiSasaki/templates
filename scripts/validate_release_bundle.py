#!/usr/bin/env python3
"""Validate provider-neutral release bundle closure and handoff readiness."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Hashable, Mapping, Sequence

try:
    from scripts import validate_contracts
    from scripts import validate_release_evidence
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    import validate_contracts  # type: ignore[no-redef]
    import validate_release_evidence  # type: ignore[no-redef]


def _unresolved_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _invocation_root() -> Path:
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


ROOT = _invocation_root()
RELEASE_BUNDLE_CONTRACT_ID = "release_bundle"
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
        whole_seconds = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        errors.append(f"{owner}: {field} must be a UTC timestamp")
        return None
    fractional_digits = match.group(2) or ""
    nanoseconds = int(fractional_digits.ljust(9, "0") or "0")
    return whole_seconds, nanoseconds


def _duplicate_values(values: list[Hashable]) -> set[Hashable]:
    seen: set[Hashable] = set()
    duplicates: set[Hashable] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _active_bundle_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = manifest.get("contracts", [])
    if not isinstance(entries, list):
        return []
    return [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id") != RELEASE_BUNDLE_CONTRACT_ID
    ]


def validate_release_bundle_documents(
    manifest: dict[str, Any],
    documents: dict[str, Any],
    *,
    artifact_digests: Mapping[str, str],
    expected_revision: str | None = None,
) -> list[str]:
    """Validate one template requirement document or product handoff bundle."""

    errors = validate_release_evidence.validate_release_evidence_documents(
        manifest,
        documents,
        expected_revision=expected_revision,
    )
    bundle = documents.get(RELEASE_BUNDLE_CONTRACT_ID)
    release = documents.get("release_evidence")
    if not isinstance(bundle, dict):
        return errors + ["release bundle: active contract document is missing or malformed"]
    if not isinstance(release, dict):
        return errors + ["release bundle: release evidence is missing or malformed"]

    try:
        mode = bundle["mode"]
        artifacts = bundle["artifacts"]
    except (KeyError, TypeError, AttributeError) as exc:
        return errors + [f"release bundle: metadata is incomplete or malformed: {exc}"]

    if mode == "template":
        for field in ("subject", "provenance", "handoff"):
            if bundle.get(field) is not None:
                errors.append(f"release bundle: template mode must not claim {field}")
        if artifacts:
            errors.append("release bundle: template mode requires artifacts to be empty")
        return errors

    if mode != "product":
        return errors + [f"release bundle: unsupported mode {mode!r}"]

    if expected_revision is None:
        errors.append("release bundle: product mode requires an expected revision")

    subject = bundle.get("subject")
    provenance = bundle.get("provenance")
    handoff = bundle.get("handoff")
    if not isinstance(subject, dict):
        errors.append("release bundle: product mode requires subject")
        subject = {}
    if not isinstance(provenance, dict):
        errors.append("release bundle: product mode requires provenance")
        provenance = {}
    if not isinstance(handoff, dict):
        errors.append("release bundle: product mode requires handoff")
        handoff = {}
    if not isinstance(artifacts, list):
        errors.append("release bundle: artifacts must be an array")
        artifacts = []

    revision = subject.get("revision")
    if expected_revision is not None and revision != expected_revision:
        errors.append("release bundle subject: revision does not match expected revision")
    release_subject = release.get("subject")
    release_revision = (
        release_subject.get("revision") if isinstance(release_subject, dict) else None
    )
    if revision != release_revision:
        errors.append("release bundle subject: revision does not match release evidence")
    _validate_visible_text(
        subject.get("description"),
        owner="release bundle subject",
        field="description",
        errors=errors,
    )

    for field in ("id", "locator"):
        _validate_visible_text(
            provenance.get(field),
            owner="release bundle provenance",
            field=field,
            errors=errors,
        )
    generated_at = _parse_timestamp(
        provenance.get("generatedAt"),
        owner="release bundle provenance",
        field="generatedAt",
        errors=errors,
    )
    release_provenance = release.get("provenance")
    release_generated_at = _parse_timestamp(
        release_provenance.get("generatedAt")
        if isinstance(release_provenance, dict)
        else None,
        owner="release evidence provenance",
        field="generatedAt",
        errors=errors,
    )
    if (
        generated_at is not None
        and release_generated_at is not None
        and generated_at < release_generated_at
    ):
        errors.append(
            "release bundle provenance: generatedAt must not precede release evidence generation"
        )

    if handoff.get("status") != "ready":
        errors.append("release bundle handoff: status must be ready")
    _validate_visible_text(
        handoff.get("description"),
        owner="release bundle handoff",
        field="description",
        errors=errors,
    )

    expected_entries = _active_bundle_entries(manifest)
    expected_ids = [entry.get("id") for entry in expected_entries]
    expected_by_id = {
        entry["id"]: entry
        for entry in expected_entries
        if isinstance(entry.get("id"), str)
    }
    artifact_ids = [
        artifact.get("contractId")
        for artifact in artifacts
        if isinstance(artifact, dict)
    ]
    artifact_paths = [
        artifact.get("path") for artifact in artifacts if isinstance(artifact, dict)
    ]

    for duplicate in sorted(
        value
        for value in _duplicate_values(artifact_ids)
        if isinstance(value, str)
    ):
        errors.append(f"duplicate release bundle artifact: {duplicate}")
    for duplicate in sorted(
        value
        for value in _duplicate_values(artifact_paths)
        if isinstance(value, str)
    ):
        errors.append(f"duplicate release bundle artifact path: {duplicate}")

    if RELEASE_BUNDLE_CONTRACT_ID in artifact_ids:
        errors.append("release bundle must not include its own contract document")

    actual_ids = {value for value in artifact_ids if isinstance(value, str)}
    expected_id_set = {value for value in expected_ids if isinstance(value, str)}
    for contract_id in sorted(expected_id_set - actual_ids):
        errors.append(f"missing release bundle artifact: {contract_id}")
    for contract_id in sorted(actual_ids - expected_id_set):
        if contract_id != RELEASE_BUNDLE_CONTRACT_ID:
            errors.append(f"unknown release bundle artifact: {contract_id}")

    if artifact_ids != expected_ids:
        errors.append("release bundle artifacts must follow manifest contract order")

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        contract_id = artifact.get("contractId")
        if not isinstance(contract_id, str):
            continue
        entry = expected_by_id.get(contract_id)
        if entry is None:
            continue
        owner = f"release bundle artifact {contract_id}"
        if artifact.get("path") != entry.get("document"):
            errors.append(f"{owner}: path does not match manifest")
        expected_digest = artifact_digests.get(contract_id)
        if expected_digest is None:
            errors.append(f"{owner}: current bytes are unavailable")
        elif artifact.get("sha256") != expected_digest:
            errors.append(f"{owner}: sha256 does not match current bytes")

    return errors


def _artifact_digests(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for entry in _active_bundle_entries(manifest):
        contract_id = entry.get("id")
        document = entry.get("document")
        if not isinstance(contract_id, str) or not isinstance(document, str):
            continue
        path = root / document
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"cannot read {document}: {exc}") from exc
        digests[contract_id] = hashlib.sha256(content).hexdigest()
    return digests


def validate_release_bundle(
    root: Path,
    *,
    expected_revision: str | None = None,
) -> list[str]:
    """Load the repository and validate release evidence plus bundle closure."""

    prerequisite_errors = validate_release_evidence.validate_release_evidence(
        root,
        expected_revision=expected_revision,
    )
    if prerequisite_errors:
        return prerequisite_errors

    try:
        manifest = validate_contracts.load_contract_manifest(root)
        documents = validate_contracts.load_contract_documents(root)
        digests = _artifact_digests(root, manifest)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        return [f"release bundle: repository metadata cannot be loaded: {exc}"]

    return validate_release_bundle_documents(
        manifest,
        documents,
        artifact_digests=digests,
        expected_revision=expected_revision,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one digest-closed release bundle for exact handoff."
    )
    parser.add_argument(
        "--expected-revision",
        help="Exact lowercase 40-hex candidate revision represented by the bundle.",
    )
    arguments = parser.parse_args(argv)

    errors = validate_release_bundle(
        ROOT,
        expected_revision=arguments.expected_revision,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("All release bundles and handoff bindings are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
