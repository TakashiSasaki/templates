#!/usr/bin/env python3
"""Explicit compatibility-boundary planning and apply for managed Composition consumers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import composer_core as core
import composer_managed as managed
import composer_transaction as transaction


class UpgradeError(core.CompositionError):
    pass


def _conflict(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    result.update(details)
    return result


def _upgrade_component_plan(
    old_lock: dict[str, Any],
    state: core.SourceState,
    selected: list[str],
) -> tuple[dict[str, list[Any]], list[dict[str, Any]]]:
    old_map = {entry["id"]: entry for entry in old_lock["resolved_components"]}
    new_map: dict[str, dict[str, Any]] = {}
    for component_id in selected:
        descriptor_path = core._component_path(component_id)
        core._assert_tracked_authority(descriptor_path)
        new_map[component_id] = {
            "id": component_id,
            "version": state.components[component_id]["version"],
            "descriptor_sha256": core.sha256_bytes(descriptor_path.read_bytes()),
        }

    components: dict[str, list[Any]] = {
        "added": sorted(set(new_map) - set(old_map)),
        "removed": sorted(set(old_map) - set(new_map)),
        "changed": [],
        "unchanged": [],
    }
    conflicts: list[dict[str, Any]] = []
    for component_id in sorted(set(old_map) & set(new_map)):
        old = old_map[component_id]
        new = new_map[component_id]
        if old["version"] != new["version"]:
            components["changed"].append(
                {
                    "id": component_id,
                    "from_version": old["version"],
                    "to_version": new["version"],
                    "from_descriptor_sha256": old["descriptor_sha256"],
                    "to_descriptor_sha256": new["descriptor_sha256"],
                    "compatibility_boundary": "component-version",
                }
            )
        elif old["descriptor_sha256"] != new["descriptor_sha256"]:
            components["changed"].append(
                {
                    "id": component_id,
                    "from_version": old["version"],
                    "to_version": new["version"],
                    "from_descriptor_sha256": old["descriptor_sha256"],
                    "to_descriptor_sha256": new["descriptor_sha256"],
                    "compatibility_boundary": "invalid-same-version-descriptor-drift",
                }
            )
            conflicts.append(
                _conflict(
                    "COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION",
                    f"component descriptor changed without a version change: {component_id}",
                    component=component_id,
                )
            )
        else:
            components["unchanged"].append(component_id)
    return components, conflicts


def _upgrade_file_plan(
    target: Path,
    old_lock: dict[str, Any],
    materials: list[core.Material],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, str]]:
    files, conflicts, carried_seed_digests = managed._file_plan(target, old_lock, materials)
    mapping = {
        "FILE_OWNER_TRANSITION_UPGRADE_REQUIRED": "FILE_OWNER_TRANSITION_NOT_SUPPORTED",
        "OWNERSHIP_TRANSITION_UPGRADE_REQUIRED": "OWNERSHIP_TRANSITION_NOT_SUPPORTED",
    }
    for entry in files["conflict"]:
        if entry.get("code") in mapping:
            entry["code"] = mapping[entry["code"]]
            entry["message"] += "; explicit upgrade does not infer owner/ownership migration"
    for entry in conflicts:
        if entry.get("code") in mapping:
            entry["code"] = mapping[entry["code"]]
            entry["message"] += "; explicit upgrade does not infer owner/ownership migration"
    files["conflict"].sort(key=lambda entry: (entry["destination"], entry.get("code", "")))
    conflicts.sort(key=lambda entry: (entry.get("destination", ""), entry["code"], entry["message"]))
    return files, conflicts, carried_seed_digests


def _build_upgrade_lock(
    old_lock: dict[str, Any],
    state: core.SourceState,
    config_bytes: bytes,
    config: dict[str, Any],
    recipe_id: str,
    selected: list[str],
    materials: list[core.Material],
    carried_seed_digests: dict[str, str],
    *,
    configuration_sha256_override: str | None = None,
) -> dict[str, Any]:
    lock = core.build_lock(
        state,
        recipe_id,
        config_bytes,
        config,
        selected,
        materials,
    )
    if configuration_sha256_override is not None:
        lock["configuration_sha256"] = configuration_sha256_override
    for entry in lock["files"]:
        carried = carried_seed_digests.get(entry["destination"])
        if carried is not None:
            entry["materialized_sha256"] = carried
    core._schema_validate(
        core.SOURCE_ROOT / "schemas/composition-lock.schema.json",
        lock,
        label="planned upgrade lock",
    )
    return lock


def _assert_supported_lock_transition(old_lock: dict[str, Any], new_lock: dict[str, Any]) -> None:
    old_files = {entry["destination"]: entry for entry in old_lock["files"]}
    new_files = {entry["destination"]: entry for entry in new_lock["files"]}
    for destination in sorted(set(old_files) & set(new_files)):
        old = old_files[destination]
        new = new_files[destination]
        if old["component"] != new["component"]:
            raise UpgradeError(
                "FILE_OWNER_TRANSITION_NOT_SUPPORTED",
                f"explicit upgrade does not infer file-owner migration at {destination}: "
                f"{old['component']} -> {new['component']}",
            )
        if old["ownership"] != new["ownership"]:
            raise UpgradeError(
                "OWNERSHIP_TRANSITION_NOT_SUPPORTED",
                f"explicit upgrade does not infer ownership migration at {destination}: "
                f"{old['ownership']} -> {new['ownership']}",
            )
        if old["ownership"] == "seed" and old["materialized_sha256"] != new["materialized_sha256"]:
            raise UpgradeError(
                "INVALID_UPGRADE_LOCK",
                f"upgrade must carry the old seed provenance digest forward at {destination}",
            )


def plan_upgrade(target: Path, config_path: Path) -> tuple[int, dict[str, Any]]:
    state = core.load_source_state()
    old_lock = managed._load_old_lock(target)
    managed._verify_source_transition(old_lock["source"]["revision"], state.revision)

    config_bytes, config = core.load_configuration(config_path)
    recipe, selected = core.resolve_configuration(state, config)
    materials = core.build_materials(state, selected)
    components, component_conflicts = _upgrade_component_plan(old_lock, state, selected)
    files, file_conflicts, carried_seed_digests = _upgrade_file_plan(target, old_lock, materials)
    lock_preview = _build_upgrade_lock(
        old_lock,
        state,
        config_bytes,
        config,
        recipe["id"],
        selected,
        materials,
        carried_seed_digests,
    )
    conflicts = component_conflicts + file_conflicts
    conflicts.sort(
        key=lambda entry: (
            entry.get("component", ""),
            entry.get("destination", ""),
            entry["code"],
            entry["message"],
        )
    )
    payload = {
        "schema_version": 1,
        "operation": "upgrade",
        "from_revision": old_lock["source"]["revision"],
        "to_revision": state.revision,
        "intent": {
            "from": old_lock["intent"],
            "to": core.normalize_intent(config),
        },
        "configuration_sha256": {
            "from": old_lock["configuration_sha256"],
            "to": lock_preview["configuration_sha256"],
        },
        "recipe": {
            "from_id": old_lock["intent"]["recipe"],
            "to_id": recipe["id"],
            "from_sha256": old_lock["recipe_sha256"],
            "to_sha256": lock_preview["recipe_sha256"],
            "changed": (
                old_lock["intent"]["recipe"] != recipe["id"]
                or old_lock["recipe_sha256"] != lock_preview["recipe_sha256"]
            ),
        },
        "components": components,
        "files": files,
        "conflicts": conflicts,
        "lock_preview": lock_preview,
    }
    return (0 if not conflicts else 2), payload


def _build_upgrade_transaction(
    plan: dict[str, Any],
    old_lock_bytes: bytes,
    old_lock: dict[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "operation": "upgrade",
        "source": {
            "repository": core.CANONICAL_REPOSITORY,
            "revision": plan["to_revision"],
        },
        "old_lock_file_sha256": core.sha256_bytes(old_lock_bytes),
        "new_lock_file_sha256": core.sha256_bytes(transaction._lock_bytes(plan["lock_preview"])),
        "old_lock": old_lock,
        "new_lock": plan["lock_preview"],
        "actions": transaction._mutation_actions(plan),
    }
    transaction._validate_transaction_shape(value)
    _assert_supported_lock_transition(old_lock, plan["lock_preview"])
    return value


def _desired_materials_for_upgrade_transaction(
    value: dict[str, Any],
) -> dict[str, core.Material]:
    state = core.load_source_state()
    if state.revision != value["source"]["revision"]:
        raise UpgradeError(
            "RECOVERY_SOURCE_MISMATCH",
            "upgrade recovery requires the exact source revision recorded by the transaction: "
            f"{value['source']['revision']}",
        )
    old_lock = value["old_lock"]
    new_lock = value["new_lock"]
    managed._verify_source_transition(old_lock["source"]["revision"], state.revision)
    _assert_supported_lock_transition(old_lock, new_lock)

    config = managed._intent_as_configuration(new_lock["intent"])
    synthetic_config_bytes = (
        json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    recipe, selected = core.resolve_configuration(state, config)
    _, component_conflicts = _upgrade_component_plan(old_lock, state, selected)
    if component_conflicts:
        raise UpgradeError(
            "INVALID_TRANSACTION",
            f"upgrade transaction violates component source invariants: {component_conflicts}",
        )
    materials = core.build_materials(state, selected)
    old_file_map = {entry["destination"]: entry for entry in old_lock["files"]}
    carried_seed_digests = {
        material.destination: old_file_map[material.destination]["materialized_sha256"]
        for material in materials
        if material.ownership == "seed"
        and material.destination in old_file_map
        and old_file_map[material.destination]["ownership"] == "seed"
        and old_file_map[material.destination]["component"] == material.component
    }
    expected_new_lock = _build_upgrade_lock(
        old_lock,
        state,
        synthetic_config_bytes,
        config,
        recipe["id"],
        selected,
        materials,
        carried_seed_digests,
        configuration_sha256_override=new_lock["configuration_sha256"],
    )
    if expected_new_lock != new_lock:
        raise UpgradeError(
            "INVALID_TRANSACTION",
            "upgrade transaction new lock does not match deterministic reconciliation at the recorded source revision",
        )
    material_map = {material.destination: material for material in materials}
    for action in value["actions"]:
        if action["action"] in {"create", "replace"}:
            desired = material_map.get(action["destination"])
            if desired is None or core.sha256_bytes(desired.data) != action["to_sha256"]:
                raise UpgradeError(
                    "INVALID_TRANSACTION",
                    f"upgrade transaction desired bytes do not match source material: {action['destination']}",
                )
    return material_map


def _apply_upgrade_transaction(
    target: Path,
    value: dict[str, Any],
    marker_bytes: bytes,
) -> dict[str, Any]:
    material_map = _desired_materials_for_upgrade_transaction(value)
    applied: list[str] = []
    resumed: list[str] = []
    for action in value["actions"]:
        destination = action["destination"]
        path = target / destination
        if action["action"] == "create":
            material = material_map[destination]
            outcome = transaction._create_expected(
                target,
                path,
                material.data,
                expected_sha256=action["to_sha256"],
            )
        elif action["action"] == "replace":
            material = material_map[destination]
            outcome = transaction._atomic_replace_expected(
                target,
                path,
                material.data,
                expected_sha256=action["from_sha256"],
                already_sha256=action["to_sha256"],
            )
        elif action["action"] == "remove":
            outcome = transaction._remove_expected(
                target,
                path,
                expected_sha256=action["from_sha256"],
            )
        else:
            raise AssertionError(action["action"])
        (resumed if outcome == "already-applied" else applied).append(destination)

    lock_path = target / core.LOCK_RELATIVE
    current_lock_bytes = transaction._read_regular_bytes(target, lock_path, label="composition lock")
    current_lock_digest = core.sha256_bytes(current_lock_bytes)
    if current_lock_digest == value["new_lock_file_sha256"]:
        resumed.append(core.LOCK_RELATIVE)
    elif current_lock_digest == value["old_lock_file_sha256"]:
        outcome = transaction._atomic_replace_expected(
            target,
            lock_path,
            transaction._lock_bytes(value["new_lock"]),
            expected_sha256=value["old_lock_file_sha256"],
            already_sha256=value["new_lock_file_sha256"],
        )
        (resumed if outcome == "already-applied" else applied).append(core.LOCK_RELATIVE)
    else:
        raise UpgradeError(
            "PRECONDITION_CHANGED",
            "composition lock changed during upgrade transaction",
        )

    errors = transaction._validate_new_state(target, value["new_lock"])
    if errors:
        raise UpgradeError("POST_UPGRADE_VALIDATION_FAILED", "; ".join(errors))

    marker_path = target / core.TRANSACTION_RELATIVE
    current_marker = transaction._read_regular_bytes(target, marker_path, label="composition transaction")
    if current_marker != marker_bytes:
        raise UpgradeError(
            "PRECONDITION_CHANGED",
            "composition transaction marker changed during upgrade recovery",
        )
    try:
        marker_path.unlink()
    except OSError as exc:
        raise UpgradeError("WRITE_FAILED", f"cannot remove completed upgrade transaction marker: {exc}") from exc
    transaction._fsync_directory(marker_path.parent)
    return {
        "status": "upgraded",
        "operation": "upgrade",
        "target": str(target),
        "from_revision": value["old_lock"]["source"]["revision"],
        "to_revision": value["new_lock"]["source"]["revision"],
        "applied": sorted(applied),
        "resumed": sorted(resumed),
        "lock": core.LOCK_RELATIVE,
    }


def _start_upgrade(target: Path, config_path: Path) -> tuple[int, dict[str, Any]]:
    lock_path = target / core.LOCK_RELATIVE
    before_lock_bytes = transaction._read_regular_bytes(target, lock_path, label="composition lock")
    status, plan = plan_upgrade(target, config_path)
    if status != 0:
        return status, plan
    after_lock_bytes = transaction._read_regular_bytes(target, lock_path, label="composition lock")
    if before_lock_bytes != after_lock_bytes:
        raise UpgradeError(
            "PRECONDITION_CHANGED",
            "composition lock changed while constructing the upgrade plan",
        )
    old_lock = core.load_json_bytes(after_lock_bytes, label=str(lock_path))
    if not isinstance(old_lock, dict):
        raise UpgradeError("INVALID_OLD_LOCK", "composition lock must be a JSON object")
    new_lock_bytes = transaction._lock_bytes(plan["lock_preview"])
    if after_lock_bytes == new_lock_bytes and not transaction._mutation_actions(plan):
        return 0, {
            "status": "upgraded",
            "operation": "upgrade",
            "target": str(target),
            "from_revision": plan["from_revision"],
            "to_revision": plan["to_revision"],
            "applied": [],
            "resumed": [],
            "no_op": True,
            "lock": core.LOCK_RELATIVE,
        }

    value = _build_upgrade_transaction(plan, after_lock_bytes, old_lock)
    marker_path = target / core.TRANSACTION_RELATIVE
    marker_bytes = transaction._transaction_bytes(value)
    transaction._write_no_overwrite_durable(target, marker_path, marker_bytes)
    payload = _apply_upgrade_transaction(target, value, marker_bytes)
    payload["no_op"] = False
    return 0, payload


def apply_upgrade(target: Path, config_path: Path | None) -> tuple[int, dict[str, Any]]:
    marker_path = target / core.TRANSACTION_RELATIVE
    if marker_path.exists() or marker_path.is_symlink():
        if config_path is not None:
            raise UpgradeError(
                "RECOVERY_CONFIG_NOT_ALLOWED",
                "an interrupted upgrade is recovered from its transaction marker; do not supply --config",
            )
        value, marker_bytes = transaction._load_transaction(target)
        if value["operation"] != "upgrade":
            raise UpgradeError(
                "RECOVERY_OPERATION_MISMATCH",
                f"existing transaction operation is {value['operation']}, not upgrade",
            )
        payload = _apply_upgrade_transaction(target, value, marker_bytes)
        payload["recovered"] = True
        payload["no_op"] = False
        return 0, payload
    if config_path is None:
        raise UpgradeError(
            "UPGRADE_CONFIG_REQUIRED",
            "a new upgrade requires --config with the explicitly selected consumer intent",
        )
    status, payload = _start_upgrade(target, config_path)
    if status == 0:
        payload["recovered"] = False
    return status, payload


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--mode", choices=("upgrade",), required=True)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        target = args.target.absolute()
        config_path = args.config.absolute() if args.config is not None else None
        if args.command == "plan":
            if config_path is None:
                raise UpgradeError(
                    "UPGRADE_CONFIG_REQUIRED",
                    "upgrade planning requires --config with the explicitly selected consumer intent",
                )
            status, payload = plan_upgrade(target, config_path)
        else:
            status, payload = apply_upgrade(target, config_path)
    except core.CompositionError as exc:
        _emit({"status": "error", "code": exc.code, "message": exc.message})
        return 2
    _emit(payload)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
