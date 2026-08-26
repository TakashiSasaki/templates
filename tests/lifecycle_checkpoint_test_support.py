from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def product_with_explicit_targets(product_evidence: dict[str, Any]) -> dict[str, Any]:
    """Return product evidence whose requirements retain their planned targets."""
    product = deepcopy(product_evidence)
    records = product.get("records")
    requirements = product.get("requirements")
    if not isinstance(records, list) or not isinstance(requirements, list):
        raise AssertionError("product evidence must contain records and requirements arrays")
    targets_by_record: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        target = record.get("target")
        if isinstance(record_id, str) and isinstance(target, dict):
            targets_by_record[record_id] = deepcopy(target)
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        if isinstance(requirement.get("targets"), list) and requirement["targets"]:
            continue
        record_ids = requirement.get("recordIds")
        if not isinstance(record_ids, list):
            raise AssertionError("product requirement recordIds must be an array")
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record_id in record_ids:
            target = targets_by_record.get(record_id) if isinstance(record_id, str) else None
            if target is None:
                raise AssertionError(
                    f"cannot derive planning target for requirement {requirement.get('id')!r} from record {record_id!r}"
                )
            key = json.dumps(target, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                targets.append(target)
        if not targets:
            raise AssertionError(
                f"product requirement {requirement.get('id')!r} has no target to preserve"
            )
        requirement["targets"] = targets
    return product


def planning_evidence_from_product(product_evidence: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (product-with-targets, planning-baseline) for the same requirements."""
    product = product_with_explicit_targets(product_evidence)
    planning = {
        "$schema": product["$schema"],
        "schemaVersion": product["schemaVersion"],
        "mode": "planning",
        "commands": [],
        "releaseGates": [],
        "records": [],
        "requirements": [],
    }
    for requirement in product["requirements"]:
        planning["requirements"].append(
            {
                "id": requirement["id"],
                "description": requirement["description"],
                "targets": deepcopy(requirement["targets"]),
                "recordIds": [],
                "requiredPositiveProofKinds": list(
                    requirement["requiredPositiveProofKinds"]
                ),
            }
        )
    return product, planning


def validate_consumer(target: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    runner = target / ".template-composition" / "validate.py"
    result = subprocess.run(
        [sys.executable, str(runner), str(target), "--format", "json"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"consumer validator did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
        ) from exc
    if not isinstance(payload, dict):
        raise AssertionError("consumer validator JSON payload must be an object")
    return result, payload


def create_planning_checkpoint(target: Path, checkpoint_id: str = "initial-planning") -> dict[str, Any]:
    """Validate the current planning state, then create its canonical checkpoint."""
    validation, payload = validate_consumer(target)
    if validation.returncode != 0 or payload.get("status") != "valid":
        raise AssertionError(f"planning state must validate before checkpoint: {payload}")
    writer = target / ".template-composition" / "checkpoint.py"
    result = subprocess.run(
        [sys.executable, str(writer), "planning", "--id", checkpoint_id],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "canonical planning checkpoint creation failed\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    try:
        created = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"checkpoint writer did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
        ) from exc
    if not isinstance(created, dict) or created.get("status") != "created":
        raise AssertionError(f"unexpected checkpoint writer result: {created!r}")
    return created
