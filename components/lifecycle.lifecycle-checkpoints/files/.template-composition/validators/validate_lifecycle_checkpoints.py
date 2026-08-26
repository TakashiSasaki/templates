#!/usr/bin/env python3
"""Validate lifecycle checkpoint history and planning-to-product transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract_common import contract_entries, load_json

LEDGER = Path("contracts/lifecycle-checkpoints.json")
EVIDENCE = Path("contracts/implementation-evidence.json")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _requirement_signature(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, dict):
        return ("invalid", repr(value))
    targets = value.get("targets")
    normalized_targets = [json.dumps(target, sort_keys=True, separators=(",", ":")) for target in targets] if isinstance(targets, list) else []
    kinds = value.get("requiredPositiveProofKinds")
    normalized_kinds = sorted(kinds) if isinstance(kinds, list) else []
    return (value.get("id"), value.get("description"), tuple(sorted(normalized_targets)), tuple(normalized_kinds))


def _planning_transition_errors(planning: dict[str, Any], product: dict[str, Any]) -> list[str]:
    if planning.get("mode") != "planning":
        return ["checkpoint planning snapshot implementation-evidence is not planning mode"]
    if product.get("mode") != "product":
        return ["current implementation-evidence is not product mode"]
    planned, current = planning.get("requirements"), product.get("requirements")
    if not isinstance(planned, list) or not isinstance(current, list):
        return ["planning/product implementation-evidence requirements must be arrays"]
    planned_by_id = {req.get("id"): _requirement_signature(req) for req in planned if isinstance(req, dict) and isinstance(req.get("id"), str)}
    current_by_id = {req.get("id"): _requirement_signature(req) for req in current if isinstance(req, dict) and isinstance(req.get("id"), str)}
    errors: list[str] = []
    for requirement_id in sorted(set(planned_by_id) - set(current_by_id)):
        errors.append(f"product transition removed planned requirement {requirement_id!r}")
    for requirement_id in sorted(set(current_by_id) - set(planned_by_id)):
        errors.append(f"product transition added requirement {requirement_id!r} after the validated planning checkpoint")
    for requirement_id in sorted(set(planned_by_id) & set(current_by_id)):
        if planned_by_id[requirement_id] != current_by_id[requirement_id]:
            errors.append(f"product transition changed planned requirement intent/targets/proof kinds for {requirement_id!r}")
    return errors


def _snapshot_manifest(root: Path, entry: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    snapshot_path = entry.get("snapshotPath")
    expected = f"artifacts/lifecycle/{entry.get('sequence', 0):03d}-{entry.get('id')}"
    if snapshot_path != expected:
        return None, [f"checkpoint {entry.get('id')!r}: snapshotPath must be {expected!r}"]
    manifest_path = root / snapshot_path / "manifest.json"
    if not manifest_path.is_file():
        return None, [f"checkpoint {entry.get('id')!r}: missing snapshot manifest {snapshot_path}/manifest.json"]
    digest = entry.get("manifestSha256")
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
        errors.append(f"checkpoint {entry.get('id')!r}: invalid manifestSha256")
    elif _sha256(manifest_path) != digest:
        errors.append(f"checkpoint {entry.get('id')!r}: snapshot manifest hash mismatch")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, errors + [f"checkpoint {entry.get('id')!r}: cannot read snapshot manifest: {exc}"]
    if not isinstance(manifest, dict):
        return None, errors + [f"checkpoint {entry.get('id')!r}: snapshot manifest must be an object"]
    for field in ("checkpointId", "sequence", "phase", "parentId"):
        expected_value = entry.get(field if field != "checkpointId" else "id")
        if manifest.get(field) != expected_value:
            errors.append(f"checkpoint {entry.get('id')!r}: snapshot manifest {field} does not match ledger")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append(f"checkpoint {entry.get('id')!r}: snapshot manifest files must be non-empty")
        return manifest, errors
    seen: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"checkpoint {entry.get('id')!r}: snapshot file {index} must be an object")
            continue
        path, snap, sha = item.get("path"), item.get("snapshotPath"), item.get("sha256")
        if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in Path(path).parts:
            errors.append(f"checkpoint {entry.get('id')!r}: invalid source path at snapshot file {index}")
            continue
        if path in seen:
            errors.append(f"checkpoint {entry.get('id')!r}: duplicate snapshot source path {path}")
        seen.add(path)
        if snap != path:
            errors.append(f"checkpoint {entry.get('id')!r}: snapshotPath for {path} must preserve the repository path")
            continue
        file_path = root / snapshot_path / snap
        if not file_path.is_file():
            errors.append(f"checkpoint {entry.get('id')!r}: missing snapshotted file {snap}")
            continue
        if not isinstance(sha, str) or HEX64.fullmatch(sha) is None or _sha256(file_path) != sha:
            errors.append(f"checkpoint {entry.get('id')!r}: snapshot hash mismatch for {snap}")
    validation = manifest.get("validation")
    if not isinstance(validation, dict) or validation.get("result") != "passed":
        errors.append(f"checkpoint {entry.get('id')!r}: snapshot validation result is not passed")
    else:
        validation_path = root / snapshot_path / "validation.json"
        expected_validation_sha = validation.get("sha256")
        if not validation_path.is_file():
            errors.append(f"checkpoint {entry.get('id')!r}: missing validation.json")
        elif not isinstance(expected_validation_sha, str) or HEX64.fullmatch(expected_validation_sha) is None or _sha256(validation_path) != expected_validation_sha:
            errors.append(f"checkpoint {entry.get('id')!r}: validation.json hash mismatch")
    return manifest, errors


def _snapshot_file(root: Path, entry: dict[str, Any], manifest: dict[str, Any], path: str) -> Path | None:
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    for item in files:
        if isinstance(item, dict) and item.get("path") == path:
            return root / entry["snapshotPath"] / path
    return None


def _current_contracts_match_snapshot(root: Path, entry: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Reject post-checkpoint product/planning contract edits, not toolchain upgrades."""
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return ["snapshot files are malformed"]
    errors: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        path = item["path"]
        if not path.startswith("contracts/") or path == "contracts/manifest.json":
            continue
        current = root / path
        if not current.is_file():
            errors.append(f"current state removed snapshotted contract {path} after checkpoint {entry.get('id')!r}")
        elif _sha256(current) != item.get("sha256"):
            errors.append(f"current state changed {path} after checkpoint {entry.get('id')!r}; create a new validated planning checkpoint before product changes")
    return errors


def validate(root: Path) -> list[str]:
    try:
        ledger = load_json(root / LEDGER)
        evidence = load_json(root / EVIDENCE)
    except Exception as exc:
        return [f"cannot load lifecycle checkpoint authority: {exc}"]
    if not isinstance(ledger, dict):
        return ["lifecycle checkpoint ledger must be an object"]
    checkpoints = ledger.get("checkpoints")
    if not isinstance(checkpoints, list):
        return ["lifecycle checkpoint ledger checkpoints must be an array"]
    mode = evidence.get("mode") if isinstance(evidence, dict) else None
    if not checkpoints:
        return ["product state requires a validated planning checkpoint; current-state validation alone is insufficient"] if mode == "product" else []

    errors: list[str] = []
    ids: set[str] = set()
    manifests: dict[str, dict[str, Any]] = {}
    previous: dict[str, Any] | None = None
    for index, entry in enumerate(checkpoints, start=1):
        if not isinstance(entry, dict):
            errors.append(f"checkpoint {index}: must be an object")
            continue
        checkpoint_id = entry.get("id")
        if checkpoint_id in ids:
            errors.append(f"duplicate lifecycle checkpoint id: {checkpoint_id}")
        if isinstance(checkpoint_id, str):
            ids.add(checkpoint_id)
        if entry.get("sequence") != index:
            errors.append(f"checkpoint {checkpoint_id!r}: sequence must be contiguous and equal {index}")
        phase, parent, change_kind = entry.get("phase"), entry.get("parentId"), entry.get("changeKind")
        if previous is None:
            if phase != "planning" or change_kind != "initial" or parent is not None:
                errors.append("first lifecycle checkpoint must be initial planning with parentId null")
        elif previous.get("phase") == "planning":
            if phase != "product" or parent != previous.get("id"):
                errors.append(f"checkpoint {checkpoint_id!r}: planning must transition directly to product with the planning checkpoint as parent")
            if change_kind != previous.get("changeKind"):
                errors.append(f"checkpoint {checkpoint_id!r}: product changeKind must match its planning parent")
        elif phase != "planning" or change_kind != "specification-change" or parent != previous.get("id"):
            errors.append(f"checkpoint {checkpoint_id!r}: a completed product must be followed only by specification-change planning parented to that product")
        snapshot_manifest, snapshot_errors = _snapshot_manifest(root, entry)
        errors.extend(snapshot_errors)
        if snapshot_manifest is not None and isinstance(checkpoint_id, str):
            manifests[checkpoint_id] = snapshot_manifest
        previous = entry

    for entry in checkpoints:
        if not isinstance(entry, dict) or entry.get("id") not in manifests:
            continue
        snap = manifests[entry["id"]]
        snap_paths = {item.get("path") for item in snap.get("files", []) if isinstance(item, dict)}
        manifest_snapshot = _snapshot_file(root, entry, snap, "contracts/manifest.json")
        if manifest_snapshot is None:
            errors.append(f"checkpoint {entry['id']!r}: snapshot omits contracts/manifest.json")
            continue
        try:
            historical_manifest = json.loads(manifest_snapshot.read_text(encoding="utf-8"))
            historical_contracts = contract_entries(historical_manifest)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            errors.append(f"checkpoint {entry['id']!r}: cannot read historical contract manifest: {exc}")
            continue
        required_paths = {"contracts/manifest.json"}
        for contract_id, contract in historical_contracts.items():
            if contract_id == "lifecycle_checkpoints":
                continue
            if isinstance(contract.get("document"), str):
                required_paths.add(contract["document"])
            if isinstance(contract.get("schema"), str):
                required_paths.add(contract["schema"])
        for path in sorted(required_paths - snap_paths):
            errors.append(f"checkpoint {entry['id']!r}: snapshot omits registered authority file {path}")

    latest = checkpoints[-1]
    if not isinstance(latest, dict) or latest.get("id") not in manifests:
        return errors
    latest_manifest = manifests[latest["id"]]
    if latest.get("phase") == "planning":
        if mode == "planning":
            errors.extend(_current_contracts_match_snapshot(root, latest, latest_manifest))
        elif mode == "product":
            planning_evidence_path = _snapshot_file(root, latest, latest_manifest, "contracts/implementation-evidence.json")
            if planning_evidence_path is None:
                errors.append(f"checkpoint {latest.get('id')!r}: planning snapshot omits implementation-evidence")
            else:
                try:
                    planning_evidence = json.loads(planning_evidence_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    errors.append(f"checkpoint {latest.get('id')!r}: cannot read planning implementation-evidence: {exc}")
                else:
                    if isinstance(evidence, dict) and isinstance(planning_evidence, dict):
                        errors.extend(_planning_transition_errors(planning_evidence, evidence))
                    else:
                        errors.append("planning/product implementation-evidence must be objects")
        else:
            errors.append(f"latest planning checkpoint requires planning or product implementation-evidence, got {mode!r}")
    elif latest.get("phase") == "product":
        if mode == "product":
            errors.extend(_current_contracts_match_snapshot(root, latest, latest_manifest))
        elif mode != "planning":
            errors.append(f"completed product checkpoint permits only product state or a new planning state, got {mode!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Lifecycle checkpoint validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
