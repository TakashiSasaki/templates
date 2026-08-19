#!/usr/bin/env python3
"""Crash-recoverable filesystem mutation for Composition managed-state plans."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import composer_core as core
import composer_managed as managed


class TransactionError(core.CompositionError):
    pass


def _lock_bytes(lock: dict[str, Any]) -> bytes:
    return (json.dumps(lock, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _transaction_bytes(transaction: dict[str, Any]) -> bytes:
    return (json.dumps(transaction, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _read_regular_bytes(target: Path, path: Path, *, label: str) -> bytes:
    if not core._parent_chain_is_safe(target, path):
        raise TransactionError("WRITE_CONFLICT", f"unsafe parent path for {label}: {path}")
    if path.is_symlink():
        raise TransactionError("WRITE_CONFLICT", f"refusing symbolic link for {label}: {path}")
    if not path.is_file():
        raise TransactionError("WRITE_CONFLICT", f"expected regular file for {label}: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise TransactionError("READ_FAILED", f"cannot read {label} {path}: {exc}") from exc


def _write_no_overwrite_durable(target: Path, path: Path, data: bytes) -> None:
    core._write_no_overwrite(target, path, data)
    _fsync_directory(path.parent)


def _atomic_replace_expected(
    target: Path,
    path: Path,
    data: bytes,
    *,
    expected_sha256: str,
    already_sha256: str,
) -> str:
    if not core._parent_chain_is_safe(target, path):
        raise TransactionError("WRITE_CONFLICT", f"unsafe parent path while replacing {path}")
    if path.is_symlink():
        raise TransactionError("WRITE_CONFLICT", f"refusing to replace symbolic link: {path}")
    if not path.is_file():
        raise TransactionError("WRITE_CONFLICT", f"replacement destination is not a regular file: {path}")
    current = core.sha256_bytes(path.read_bytes())
    if current == already_sha256:
        return "already-applied"
    if current != expected_sha256:
        raise TransactionError(
            "PRECONDITION_CHANGED",
            f"replacement precondition changed for {path}; expected {expected_sha256}, found {current}",
        )

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".template-composition-update-",
            dir=path.parent,
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if core.sha256_bytes(Path(temp_name).read_bytes()) != already_sha256:
            raise TransactionError("WRITE_FAILED", f"staged replacement digest mismatch for {path}")
        if not core._parent_chain_is_safe(target, path) or path.is_symlink() or not path.is_file():
            raise TransactionError("PRECONDITION_CHANGED", f"replacement path changed unsafely: {path}")
        current = core.sha256_bytes(path.read_bytes())
        if current == already_sha256:
            return "already-applied"
        if current != expected_sha256:
            raise TransactionError(
                "PRECONDITION_CHANGED",
                f"replacement precondition changed for {path}; expected {expected_sha256}, found {current}",
            )
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
        return "applied"
    except OSError as exc:
        raise TransactionError("WRITE_FAILED", f"cannot atomically replace {path}: {exc}") from exc
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def _remove_expected(
    target: Path,
    path: Path,
    *,
    expected_sha256: str,
) -> str:
    if not core._parent_chain_is_safe(target, path):
        raise TransactionError("WRITE_CONFLICT", f"unsafe parent path while removing {path}")
    if path.is_symlink():
        raise TransactionError("WRITE_CONFLICT", f"refusing to remove symbolic link: {path}")
    if not path.exists():
        return "already-applied"
    if not path.is_file():
        raise TransactionError("WRITE_CONFLICT", f"removal destination is not a regular file: {path}")
    current = core.sha256_bytes(path.read_bytes())
    if current != expected_sha256:
        raise TransactionError(
            "PRECONDITION_CHANGED",
            f"removal precondition changed for {path}; expected {expected_sha256}, found {current}",
        )
    try:
        path.unlink()
    except OSError as exc:
        raise TransactionError("WRITE_FAILED", f"cannot remove {path}: {exc}") from exc
    _fsync_directory(path.parent)
    return "applied"


def _create_expected(
    target: Path,
    path: Path,
    data: bytes,
    *,
    expected_sha256: str,
) -> str:
    if path.is_symlink():
        raise TransactionError("WRITE_CONFLICT", f"refusing symbolic-link destination: {path}")
    if path.exists():
        if path.is_file() and core._parent_chain_is_safe(target, path):
            current = core.sha256_bytes(path.read_bytes())
            if current == expected_sha256:
                return "already-applied"
        raise TransactionError("PRECONDITION_CHANGED", f"create destination is no longer empty: {path}")
    _write_no_overwrite_durable(target, path, data)
    installed = core.sha256_bytes(path.read_bytes())
    if installed != expected_sha256:
        raise TransactionError("WRITE_FAILED", f"created destination digest mismatch: {path}")
    return "applied"


def _load_source_validator_module() -> ModuleType:
    core._assert_tracked_authority(core.SOURCE_CONSUMER_VALIDATOR)
    spec = importlib.util.spec_from_file_location(
        "composition_source_validator_for_transaction",
        core.SOURCE_CONSUMER_VALIDATOR,
    )
    if spec is None or spec.loader is None:
        raise TransactionError("VALIDATOR_UNAVAILABLE", "cannot load source composition validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_new_state(target: Path, lock: dict[str, Any]) -> list[str]:
    module = _load_source_validator_module()
    errors = list(module.validate_lock_shape(lock))
    if not errors:
        errors.extend(module.validate_materialized_files(target, lock))
    return errors


def _mutation_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for action_name in ("create", "replace", "remove"):
        for entry in plan["files"][action_name]:
            action = {"action": action_name, **entry}
            actions.append(action)
    actions.sort(key=lambda entry: (entry["destination"], entry["action"]))
    return actions


def _validate_action_against_locks(
    action: dict[str, Any],
    old_files: dict[str, dict[str, Any]],
    new_files: dict[str, dict[str, Any]],
) -> None:
    destination = action["destination"]
    old = old_files.get(destination)
    new = new_files.get(destination)
    if action["action"] == "create":
        if old is not None or new is None:
            raise TransactionError("INVALID_TRANSACTION", f"invalid create transition for {destination}")
        if (
            action["component"] != new["component"]
            or action["ownership"] != new["ownership"]
            or action["to_sha256"] != new["materialized_sha256"]
        ):
            raise TransactionError("INVALID_TRANSACTION", f"create action does not match new lock: {destination}")
        return
    if action["action"] == "replace":
        if old is None or new is None:
            raise TransactionError("INVALID_TRANSACTION", f"invalid replace transition for {destination}")
        if old["ownership"] not in {"managed", "generated"}:
            raise TransactionError("INVALID_TRANSACTION", f"cannot replace old seed via update: {destination}")
        if (
            old["component"] != new["component"]
            or old["ownership"] != new["ownership"]
            or action["component"] != new["component"]
            or action["ownership"] != new["ownership"]
            or action["from_sha256"] != old["materialized_sha256"]
            or action["to_sha256"] != new["materialized_sha256"]
        ):
            raise TransactionError("INVALID_TRANSACTION", f"replace action does not match lock transition: {destination}")
        return
    if action["action"] == "remove":
        if old is None or new is not None:
            raise TransactionError("INVALID_TRANSACTION", f"invalid remove transition for {destination}")
        if old["ownership"] not in {"managed", "generated"}:
            raise TransactionError("INVALID_TRANSACTION", f"cannot remove seed via update: {destination}")
        if (
            action["component"] != old["component"]
            or action["ownership"] != old["ownership"]
            or action["from_sha256"] != old["materialized_sha256"]
        ):
            raise TransactionError("INVALID_TRANSACTION", f"remove action does not match old lock: {destination}")
        return
    raise TransactionError("INVALID_TRANSACTION", f"unknown transaction action: {action['action']}")


def _validate_transaction_shape(transaction: dict[str, Any]) -> None:
    try:
        core._schema_validate(
            core.SOURCE_ROOT / "schemas/composition-transaction.schema.json",
            transaction,
            label="composition transaction",
        )
    except core.CompositionError as exc:
        raise TransactionError("INVALID_TRANSACTION", exc.message) from exc
    if transaction["source"]["repository"] != core.CANONICAL_REPOSITORY:
        raise TransactionError("INVALID_TRANSACTION", "transaction source identity is unsupported")
    try:
        core._schema_validate(
            core.SOURCE_ROOT / "schemas/composition-lock.schema.json",
            transaction["old_lock"],
            label="transaction old lock",
        )
        core._schema_validate(
            core.SOURCE_ROOT / "schemas/composition-lock.schema.json",
            transaction["new_lock"],
            label="transaction new lock",
        )
        managed._validate_lock_semantics(transaction["old_lock"])
        managed._validate_lock_semantics(transaction["new_lock"])
    except core.CompositionError as exc:
        raise TransactionError("INVALID_TRANSACTION", exc.message) from exc
    new_bytes = _lock_bytes(transaction["new_lock"])
    if core.sha256_bytes(new_bytes) != transaction["new_lock_file_sha256"]:
        raise TransactionError("INVALID_TRANSACTION", "new lock file digest does not match transaction new_lock")
    if transaction["new_lock"]["source"] != transaction["source"]:
        raise TransactionError("INVALID_TRANSACTION", "transaction source does not match new lock source")

    old_files = {entry["destination"]: entry for entry in transaction["old_lock"]["files"]}
    new_files = {entry["destination"]: entry for entry in transaction["new_lock"]["files"]}
    destinations: list[str] = []
    for action in transaction["actions"]:
        _validate_action_against_locks(action, old_files, new_files)
        destinations.append(action["destination"])
    if destinations != sorted(destinations) or len(destinations) != len(set(destinations)):
        raise TransactionError("INVALID_TRANSACTION", "transaction action destinations must be unique and ordered")


def _desired_materials_for_transaction(
    transaction: dict[str, Any],
) -> dict[str, core.Material]:
    state = core.load_source_state()
    if state.revision != transaction["source"]["revision"]:
        raise TransactionError(
            "RECOVERY_SOURCE_MISMATCH",
            "recovery requires the exact source revision recorded by the transaction: "
            f"{transaction['source']['revision']}",
        )
    old_lock = transaction["old_lock"]
    managed._verify_source_transition(old_lock["source"]["revision"], state.revision)
    config = managed._intent_as_configuration(old_lock["intent"])
    recipe, selected = core.resolve_configuration(state, config)
    components, component_conflicts = managed._component_plan(old_lock, state, selected)
    if component_conflicts:
        raise TransactionError(
            "INVALID_TRANSACTION",
            f"transaction crosses update compatibility boundary: {component_conflicts}",
        )
    del components
    materials = core.build_materials(state, selected)
    carried_seed_digests = {
        entry["destination"]: entry["materialized_sha256"]
        for entry in old_lock["files"]
        if entry["ownership"] == "seed"
        and any(
            candidate.destination == entry["destination"] and candidate.ownership == "seed"
            for candidate in materials
        )
    }
    expected_new_lock = managed._build_update_lock(
        old_lock,
        state,
        config,
        recipe["id"],
        selected,
        materials,
        carried_seed_digests,
    )
    if expected_new_lock != transaction["new_lock"]:
        raise TransactionError(
            "INVALID_TRANSACTION",
            "transaction new lock does not match deterministic reconciliation at the recorded source revision",
        )
    material_map = {entry.destination: entry for entry in materials}
    for action in transaction["actions"]:
        if action["action"] in {"create", "replace"}:
            desired = material_map.get(action["destination"])
            if desired is None or core.sha256_bytes(desired.data) != action["to_sha256"]:
                raise TransactionError(
                    "INVALID_TRANSACTION",
                    f"transaction desired bytes do not match source material: {action['destination']}",
                )
    return material_map


def _build_transaction(
    target: Path,
    plan: dict[str, Any],
    old_lock_bytes: bytes,
    old_lock: dict[str, Any],
) -> dict[str, Any]:
    transaction = {
        "schema_version": 1,
        "operation": "update",
        "source": {
            "repository": core.CANONICAL_REPOSITORY,
            "revision": plan["to_revision"],
        },
        "old_lock_file_sha256": core.sha256_bytes(old_lock_bytes),
        "new_lock_file_sha256": core.sha256_bytes(_lock_bytes(plan["lock_preview"])),
        "old_lock": old_lock,
        "new_lock": plan["lock_preview"],
        "actions": _mutation_actions(plan),
    }
    _validate_transaction_shape(transaction)
    return transaction


def _load_transaction(target: Path) -> tuple[dict[str, Any], bytes]:
    path = target / core.TRANSACTION_RELATIVE
    if path.is_symlink():
        raise TransactionError("INVALID_TRANSACTION", "composition transaction must not be a symbolic link")
    if not path.is_file():
        raise TransactionError("RECOVERY_REQUIRED", "composition transaction marker is missing")
    raw = _read_regular_bytes(target, path, label="composition transaction")
    value = core.load_json_bytes(raw, label=str(path))
    if not isinstance(value, dict):
        raise TransactionError("INVALID_TRANSACTION", "composition transaction must be a JSON object")
    _validate_transaction_shape(value)
    return value, raw


def _apply_transaction(target: Path, transaction: dict[str, Any], marker_bytes: bytes) -> dict[str, Any]:
    material_map = _desired_materials_for_transaction(transaction)
    applied: list[str] = []
    resumed: list[str] = []
    for action in transaction["actions"]:
        destination = action["destination"]
        path = target / destination
        if action["action"] == "create":
            material = material_map[destination]
            outcome = _create_expected(
                target,
                path,
                material.data,
                expected_sha256=action["to_sha256"],
            )
        elif action["action"] == "replace":
            material = material_map[destination]
            outcome = _atomic_replace_expected(
                target,
                path,
                material.data,
                expected_sha256=action["from_sha256"],
                already_sha256=action["to_sha256"],
            )
        elif action["action"] == "remove":
            outcome = _remove_expected(
                target,
                path,
                expected_sha256=action["from_sha256"],
            )
        else:
            raise AssertionError(action["action"])
        (resumed if outcome == "already-applied" else applied).append(destination)

    lock_path = target / core.LOCK_RELATIVE
    current_lock_bytes = _read_regular_bytes(target, lock_path, label="composition lock")
    current_lock_digest = core.sha256_bytes(current_lock_bytes)
    if current_lock_digest == transaction["new_lock_file_sha256"]:
        resumed.append(core.LOCK_RELATIVE)
    elif current_lock_digest == transaction["old_lock_file_sha256"]:
        outcome = _atomic_replace_expected(
            target,
            lock_path,
            _lock_bytes(transaction["new_lock"]),
            expected_sha256=transaction["old_lock_file_sha256"],
            already_sha256=transaction["new_lock_file_sha256"],
        )
        (resumed if outcome == "already-applied" else applied).append(core.LOCK_RELATIVE)
    else:
        raise TransactionError(
            "PRECONDITION_CHANGED",
            "composition lock changed during update transaction",
        )

    errors = _validate_new_state(target, transaction["new_lock"])
    if errors:
        raise TransactionError(
            "POST_UPDATE_VALIDATION_FAILED",
            "; ".join(errors),
        )

    marker_path = target / core.TRANSACTION_RELATIVE
    current_marker = _read_regular_bytes(target, marker_path, label="composition transaction")
    if current_marker != marker_bytes:
        raise TransactionError(
            "PRECONDITION_CHANGED",
            "composition transaction marker changed during recovery",
        )
    try:
        marker_path.unlink()
    except OSError as exc:
        raise TransactionError("WRITE_FAILED", f"cannot remove completed transaction marker: {exc}") from exc
    _fsync_directory(marker_path.parent)
    return {
        "status": "updated",
        "operation": transaction["operation"],
        "target": str(target),
        "from_revision": transaction["old_lock"]["source"]["revision"],
        "to_revision": transaction["new_lock"]["source"]["revision"],
        "applied": sorted(applied),
        "resumed": sorted(resumed),
        "lock": core.LOCK_RELATIVE,
    }


def _start_update(target: Path) -> tuple[int, dict[str, Any]]:
    lock_path = target / core.LOCK_RELATIVE
    before_lock_bytes = _read_regular_bytes(target, lock_path, label="composition lock")
    status, plan = managed.plan_update(target)
    if status != 0:
        return status, plan
    after_lock_bytes = _read_regular_bytes(target, lock_path, label="composition lock")
    if before_lock_bytes != after_lock_bytes:
        raise TransactionError(
            "PRECONDITION_CHANGED",
            "composition lock changed while constructing the update plan",
        )
    old_lock = core.load_json_bytes(after_lock_bytes, label=str(lock_path))
    if not isinstance(old_lock, dict):
        raise TransactionError("INVALID_OLD_LOCK", "composition lock must be a JSON object")
    new_lock_bytes = _lock_bytes(plan["lock_preview"])
    if after_lock_bytes == new_lock_bytes and not _mutation_actions(plan):
        return 0, {
            "status": "updated",
            "operation": "update",
            "target": str(target),
            "from_revision": plan["from_revision"],
            "to_revision": plan["to_revision"],
            "applied": [],
            "resumed": [],
            "no_op": True,
            "lock": core.LOCK_RELATIVE,
        }

    transaction = _build_transaction(target, plan, after_lock_bytes, old_lock)
    marker_path = target / core.TRANSACTION_RELATIVE
    marker_bytes = _transaction_bytes(transaction)
    _write_no_overwrite_durable(target, marker_path, marker_bytes)
    try:
        payload = _apply_transaction(target, transaction, marker_bytes)
    except core.CompositionError:
        raise
    payload["no_op"] = False
    return 0, payload


def apply_update(target: Path) -> tuple[int, dict[str, Any]]:
    marker_path = target / core.TRANSACTION_RELATIVE
    if marker_path.exists() or marker_path.is_symlink():
        transaction, marker_bytes = _load_transaction(target)
        if transaction["operation"] != "update":
            raise TransactionError(
                "RECOVERY_OPERATION_MISMATCH",
                f"existing transaction operation is {transaction['operation']}, not update",
            )
        payload = _apply_transaction(target, transaction, marker_bytes)
        payload["recovered"] = True
        payload["no_op"] = False
        return 0, payload
    status, payload = _start_update(target)
    if status == 0:
        payload["recovered"] = False
    return status, payload
