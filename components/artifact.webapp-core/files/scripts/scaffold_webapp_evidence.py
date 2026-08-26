#!/usr/bin/env python3
"""Render a deterministic non-canonical Webapp implementation-evidence worklist."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .webapp_evidence_targets import expected_targets, record_id, target_key
else:
    from webapp_evidence_targets import expected_targets, record_id, target_key


CANONICAL_EVIDENCE = Path("contracts/implementation-evidence.json")
STATUSES = ("verified", "missing", "deferred")


def _status_union(statuses: list[str]) -> str:
    """Combine statuses with missing taking precedence over deferred."""
    if any(status == "missing" for status in statuses):
        return "missing"
    if any(status == "deferred" for status in statuses):
        return "deferred"
    return "verified"


def _record_status(record: object) -> str:
    """Project canonical evidence into a non-authoritative worklist status."""
    if not isinstance(record, dict):
        return "missing"
    boundary = record.get("implementationBoundary")
    if not isinstance(boundary, dict) or boundary.get("status") != "verified":
        return "missing"

    proof_sets: list[object] = [
        record.get("positiveEvidence"),
        record.get("negativeEvidence"),
    ]
    if any(not isinstance(proofs, list) or not proofs for proofs in proof_sets):
        return "missing"
    proofs = [proof for proof_set in proof_sets for proof in proof_set]
    if any(
        not isinstance(proof, dict)
        or proof.get("status") not in {"verified", "deferred"}
        for proof in proofs
    ):
        return "missing"
    if any(proof.get("status") == "deferred" for proof in proofs):
        return "deferred"
    if not isinstance(record.get("releaseGateIds"), list) or not record["releaseGateIds"]:
        return "missing"
    return "verified"


def _load_canonical(root: Path) -> dict[str, Any]:
    path = root / CANONICAL_EVIDENCE
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("canonical implementation evidence must be an object")
    return value


def _canonical_records(
    evidence: dict[str, Any],
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], dict[str, str]]:
    records = evidence.get("records", [])
    if not isinstance(records, list):
        raise ValueError("canonical implementation evidence records must be an array")
    by_target: dict[tuple[Any, ...], dict[str, Any]] = {}
    statuses: dict[str, str] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("target"), dict):
            raise ValueError(
                "canonical implementation evidence record "
                f"{index} must contain an object target"
            )
        key = target_key(record["target"])
        if key in by_target:
            raise ValueError(
                "canonical implementation evidence contains duplicate target "
                f"{record['target']!r}"
            )
        by_target[key] = record
        record_id_value = record.get("id")
        if isinstance(record_id_value, str):
            statuses[record_id_value] = _record_status(record)
    return by_target, statuses


def _project_requirements(
    evidence: dict[str, Any], record_statuses: dict[str, str]
) -> list[dict[str, Any]]:
    requirements = evidence.get("requirements", [])
    if requirements is None:
        return []
    if not isinstance(requirements, list):
        raise ValueError("canonical implementation evidence requirements must be an array")

    projected: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"canonical requirement {index} must be an object")
        requirement_id = requirement.get("id")
        description = requirement.get("description")
        record_ids = requirement.get("recordIds")
        if not isinstance(requirement_id, str) or not isinstance(description, str):
            raise ValueError(
                f"canonical requirement {index} must have id and description text"
            )
        if not isinstance(record_ids, list) or not record_ids:
            raise ValueError(
                f"canonical requirement {requirement_id!r} must reference records"
            )
        statuses = [
            record_statuses.get(record_id, "missing")
            for record_id in record_ids
            if isinstance(record_id, str)
        ]
        if len(statuses) != len(record_ids):
            raise ValueError(
                f"canonical requirement {requirement_id!r} has a non-text record reference"
            )
        item: dict[str, Any] = {
            "id": requirement_id,
            "description": description,
            "recordIds": list(record_ids),
            "status": _status_union(statuses),
        }
        required_kinds = requirement.get("requiredPositiveProofKinds")
        if required_kinds is not None:
            if not isinstance(required_kinds, list) or not required_kinds:
                raise ValueError(
                    f"canonical requirement {requirement_id!r} has invalid proof kinds"
                )
            item["requiredPositiveProofKinds"] = list(required_kinds)
        projected.append(item)
    return sorted(projected, key=lambda item: item["id"])


def record_skeleton(target: dict[str, Any], status: str = "missing") -> dict[str, Any]:
    identifier = record_id(target)
    if status not in STATUSES:
        raise ValueError(f"unsupported Webapp evidence worklist status: {status!r}")
    return {
        "id": identifier,
        "status": status,
        "target": target,
        "implementationBoundary": {
            "status": "required",
            "description": "TODO: identify the product implementation boundary for this target.",
        },
        "positiveEvidence": [
            {
                "id": f"{identifier}-positive",
                "status": "required",
                "description": "TODO: identify positive evidence for this target.",
            }
        ],
        "negativeEvidence": [
            {
                "id": f"{identifier}-negative",
                "status": "required",
                "description": "TODO: identify negative evidence for this target.",
            }
        ],
        "releaseGateIds": [],
    }


def render_worklist(root: Path) -> dict[str, Any]:
    targets = expected_targets(root)
    evidence = _load_canonical(root)
    canonical_by_target, record_statuses = _canonical_records(evidence)
    records = [
        record_skeleton(
            target,
            _record_status(canonical_by_target[target_key(target)])
            if target_key(target) in canonical_by_target
            else "missing",
        )
        for target in targets
    ]
    identifiers = [record["id"] for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Webapp evidence worklist produces duplicate record ids")
    status = _status_union([record["status"] for record in records])
    return {
        "format": "webapp-implementation-evidence-worklist",
        "formatVersion": 1,
        "status": status,
        "statusCounts": {
            value: sum(record["status"] == value for record in records)
            for value in STATUSES
        },
        "recordCount": len(records),
        "records": records,
        "requirements": _project_requirements(evidence, record_statuses),
    }


def resolve_output(root: Path, value: str) -> Path:
    requested = Path(value)
    candidate = requested if requested.is_absolute() else root / requested
    candidate = candidate.absolute()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "--output must stay within the Webapp repository root: "
            f"{resolved} is outside {root}"
        ) from exc

    canonical = (root / CANONICAL_EVIDENCE).resolve(strict=False)
    if resolved == canonical:
        raise ValueError(
            "--output refuses the canonical implementation-evidence document; "
            "write the non-canonical worklist to a separate consumer-owned file"
        )
    return candidate


def write_worklist(root: Path, output: str, worklist: dict[str, Any]) -> None:
    destination = resolve_output(root, output)
    parent = destination.parent
    if not parent.exists():
        raise ValueError(f"--output parent does not exist: {parent}")
    if not parent.is_dir():
        raise ValueError(f"--output parent is not a directory: {parent}")
    if os.path.lexists(destination):
        raise FileExistsError(f"--output path already exists: {destination}")

    payload = json.dumps(worklist, indent=2, ensure_ascii=False) + "\n"
    created = False
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Webapp repository root; defaults to the current directory",
    )
    parser.add_argument(
        "--output",
        help=(
            "write the worklist to a new consumer-owned file relative to the Webapp "
            "repository root instead of standard output; existing paths and the canonical "
            "implementation-evidence document are refused"
        ),
    )
    args = parser.parse_args()
    try:
        root = Path(args.root).resolve()
        worklist = render_worklist(root)
        if args.output is None:
            print(json.dumps(worklist, indent=2, ensure_ascii=False))
        else:
            write_worklist(root, args.output, worklist)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Webapp evidence scaffold failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
