#!/usr/bin/env python3
"""Create validated, content-addressed lifecycle checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
LEDGER_REL = Path("contracts/lifecycle-checkpoints.json")
MANIFEST_REL = Path("contracts/manifest.json")
VALIDATOR_REL = Path(".template-composition/validate.py")
REGISTRY_REL = Path(".template-composition/validation-registry.json")
LOCK_REL = Path(".template-composition/lock.json")


class CheckpointError(RuntimeError):
    pass


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _registered_authority_paths(root: Path) -> list[str]:
    manifest = _load_json(root / MANIFEST_REL)
    contracts = manifest.get("contracts")
    if not isinstance(contracts, list):
        raise CheckpointError("contracts/manifest.json contracts must be an array")
    paths = {"contracts/manifest.json"}
    for entry in contracts:
        if not isinstance(entry, dict):
            raise CheckpointError("contracts/manifest.json contains a non-object contract")
        if entry.get("id") == "lifecycle_checkpoints":
            continue
        document = entry.get("document")
        schema = entry.get("schema")
        for label, value in (("document", document), ("schema", schema)):
            if not isinstance(value, str) or not value or value.startswith("/"):
                raise CheckpointError(f"contract {entry.get('id')!r} has invalid {label} path {value!r}")
            if ".." in Path(value).parts:
                raise CheckpointError(f"contract {entry.get('id')!r} has non-portable {label} path {value!r}")
            paths.add(value)
    for optional in (REGISTRY_REL.as_posix(), LOCK_REL.as_posix()):
        if (root / optional).is_file():
            paths.add(optional)
    missing = [path for path in sorted(paths) if not (root / path).is_file()]
    if missing:
        raise CheckpointError("cannot checkpoint missing authority files: " + ", ".join(missing))
    return sorted(paths)


def _run_validation(root: Path) -> dict[str, Any]:
    command = [sys.executable, str(root / VALIDATOR_REL), str(root), "--format", "json"]
    try:
        completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise CheckpointError(f"cannot execute canonical Composition validation: {exc}") from exc
    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CheckpointError(f"canonical Composition validation did not return JSON: {detail}") from exc
    if completed.returncode != 0 or not isinstance(output, dict) or output.get("status") != "passed":
        detail = completed.stderr.strip()
        suffix = f"; stderr: {detail}" if detail else ""
        raise CheckpointError(f"canonical Composition validation must pass before checkpoint creation{suffix}")
    return {"schemaVersion": 1, "authority": "composition-selected-validation-v1", "command": [sys.executable, VALIDATOR_REL.as_posix(), ".", "--format", "json"], "result": "passed", "output": output}


def _authority_identity(root: Path) -> dict[str, Any]:
    authority: dict[str, Any] = {"validationEntrypoint": VALIDATOR_REL.as_posix()}
    if (root / REGISTRY_REL).is_file():
        authority["validationRegistrySha256"] = _sha256(root / REGISTRY_REL)
    if (root / LOCK_REL).is_file():
        authority["compositionLockSha256"] = _sha256(root / LOCK_REL)
        try:
            lock = _load_json(root / LOCK_REL)
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        else:
            source = lock.get("source_revision")
            if not isinstance(source, str):
                source = lock.get("sourceRevision")
            if isinstance(source, str) and source:
                authority["compositionSourceRevision"] = source
    return authority


def _next_entry(checkpoints: list[dict[str, Any]], *, checkpoint_id: str, phase: str, from_id: str | None) -> dict[str, Any]:
    sequence = len(checkpoints) + 1
    if phase == "planning":
        if not checkpoints:
            change_kind, parent = "initial", None
        else:
            previous = checkpoints[-1]
            if previous.get("phase") != "product":
                raise CheckpointError("a new planning checkpoint requires the previous checkpoint to be product")
            change_kind, parent = "specification-change", previous.get("id")
        if from_id is not None:
            raise CheckpointError("--from is valid only for product checkpoints")
    else:
        if not checkpoints or checkpoints[-1].get("phase") != "planning":
            raise CheckpointError("a product checkpoint requires an immediately preceding planning checkpoint")
        previous = checkpoints[-1]
        parent = previous.get("id")
        if from_id != parent:
            raise CheckpointError(f"product checkpoint --from must name latest planning checkpoint {parent!r}")
        change_kind = previous.get("changeKind")
    return {"id": checkpoint_id, "sequence": sequence, "phase": phase, "changeKind": change_kind, "parentId": parent, "snapshotPath": f"artifacts/lifecycle/{sequence:03d}-{checkpoint_id}"}


def create_checkpoint(root: Path, *, checkpoint_id: str, phase: str, from_id: str | None, source_revision: str | None) -> dict[str, Any]:
    if ID_RE.fullmatch(checkpoint_id) is None:
        raise CheckpointError("checkpoint id must match ^[a-z][a-z0-9-]*$")
    ledger_path = root / LEDGER_REL
    ledger = _load_json(ledger_path)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("checkpoints"), list):
        raise CheckpointError("lifecycle checkpoint ledger is malformed")
    checkpoints = ledger["checkpoints"]
    if any(isinstance(entry, dict) and entry.get("id") == checkpoint_id for entry in checkpoints):
        raise CheckpointError(f"checkpoint id already exists: {checkpoint_id}")
    evidence = _load_json(root / "contracts/implementation-evidence.json")
    expected_mode = "planning" if phase == "planning" else "product"
    if not isinstance(evidence, dict) or evidence.get("mode") != expected_mode:
        raise CheckpointError(f"{phase} checkpoint requires implementation-evidence mode {expected_mode!r}")
    entry = _next_entry(checkpoints, checkpoint_id=checkpoint_id, phase=phase, from_id=from_id)
    validation = _run_validation(root)
    authority_paths = _registered_authority_paths(root)
    lifecycle_root = root / "artifacts" / "lifecycle"
    lifecycle_root.mkdir(parents=True, exist_ok=True)
    final_snapshot = root / entry["snapshotPath"]
    if final_snapshot.exists():
        raise CheckpointError(f"snapshot path already exists: {entry['snapshotPath']}")
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{entry['sequence']:03d}-{checkpoint_id}-", dir=lifecycle_root))
    try:
        files: list[dict[str, str]] = []
        for relative in authority_paths:
            source = root / relative
            destination = temp_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            files.append({"path": relative, "snapshotPath": relative, "sha256": _sha256(destination)})
        validation_path = temp_dir / "validation.json"
        _write_json(validation_path, validation)
        validation_sha = _sha256(validation_path)
        recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        snapshot_manifest: dict[str, Any] = {"schemaVersion": 1, "checkpointId": entry["id"], "sequence": entry["sequence"], "phase": entry["phase"], "changeKind": entry["changeKind"], "parentId": entry["parentId"], "recordedAt": recorded_at, "chronologyAuthority": "sequence-parent-hash-chain", "authority": _authority_identity(root), "files": files, "validation": {"result": "passed", "path": "validation.json", "sha256": validation_sha}}
        if source_revision:
            snapshot_manifest["sourceAnchor"] = {"kind": "vcs-revision", "revision": source_revision, "authority": "external"}
        manifest_path = temp_dir / "manifest.json"
        _write_json(manifest_path, snapshot_manifest)
        entry["manifestSha256"] = _sha256(manifest_path)
        entry["recordedAt"] = recorded_at
        temp_dir.rename(final_snapshot)
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    updated = {"$schema": ledger.get("$schema"), "schemaVersion": ledger.get("schemaVersion"), "checkpoints": [*checkpoints, entry]}
    fd, temp_name = tempfile.mkstemp(prefix=".lifecycle-checkpoints-", suffix=".json", dir=ledger_path.parent, text=True)
    os.close(fd)
    temp_ledger = Path(temp_name)
    try:
        _write_json(temp_ledger, updated)
        temp_ledger.replace(ledger_path)
    except BaseException:
        temp_ledger.unlink(missing_ok=True)
        raise
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)
    for phase in ("planning", "product"):
        sub = subparsers.add_parser(phase)
        sub.add_argument("--id", required=True)
        sub.add_argument("--source-revision", help="Optional external VCS revision anchor; not used as Composition chronology authority.")
        if phase == "product":
            sub.add_argument("--from", dest="from_id", required=True, help="Exact planning checkpoint id consumed by this product transition.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        entry = create_checkpoint(root, checkpoint_id=args.id, phase=args.phase, from_id=getattr(args, "from_id", None), source_revision=args.source_revision)
    except (CheckpointError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "created", "checkpoint": entry, "timestampAuthority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
