#!/usr/bin/env python3
"""Read-only reconciliation planning for managed Composition consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import composer_core as core
import composer_source


class ManagedPlanError(core.CompositionError):
    pass


def _conflict(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    result.update(details)
    return result


def _load_old_lock(target: Path) -> dict[str, Any]:
    if target.is_symlink():
        raise ManagedPlanError(
            "INVALID_TARGET",
            "consumer repository root must not be a symbolic link",
        )
    transaction = target / core.TRANSACTION_RELATIVE
    if transaction.exists() or transaction.is_symlink():
        raise ManagedPlanError(
            "RECOVERY_REQUIRED",
            f"interrupted managed-state transaction is present: {core.TRANSACTION_RELATIVE}",
        )
    lock_path = target / core.LOCK_RELATIVE
    if lock_path.is_symlink():
        raise ManagedPlanError("INVALID_OLD_LOCK", "composition lock must not be a symbolic link")
    if not lock_path.is_file():
        raise ManagedPlanError(
            "MANAGED_LOCK_REQUIRED",
            f"managed operation requires {core.LOCK_RELATIVE}",
        )
    value = core.read_json(lock_path)
    if not isinstance(value, dict):
        raise ManagedPlanError("INVALID_OLD_LOCK", "composition lock must be a JSON object")
    try:
        core._schema_validate(
            core.SOURCE_ROOT / "schemas/composition-lock.schema.json",
            value,
            label="existing composition lock",
        )
    except core.CompositionError as exc:
        raise ManagedPlanError("INVALID_OLD_LOCK", exc.message) from exc
    _validate_lock_semantics(value)
    return value


def _validate_lock_semantics(lock: dict[str, Any]) -> None:
    intent = lock["intent"]
    include = intent["components"]["include"]
    exclude = intent["components"]["exclude"]
    if include != sorted(include) or len(include) != len(set(include)):
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "lock intent components.include must be unique and lexically ordered",
        )
    if exclude != sorted(exclude) or len(exclude) != len(set(exclude)):
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "lock intent components.exclude must be unique and lexically ordered",
        )
    if set(include) & set(exclude):
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "lock intent include/exclude sets must be disjoint",
        )

    component_ids = [entry["id"] for entry in lock["resolved_components"]]
    if component_ids != sorted(component_ids) or len(component_ids) != len(set(component_ids)):
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "resolved component IDs must be unique and lexically ordered",
        )
    if sum(component_id.startswith("artifact.") for component_id in component_ids) != 1:
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "composition lock must resolve exactly one artifact component",
        )
    resolved = set(component_ids)

    files = lock["files"]
    destinations = [entry["destination"] for entry in files]
    if destinations != sorted(destinations) or len(destinations) != len(set(destinations)):
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "lock file destinations must be unique and lexically ordered",
        )
    core._validate_material_destinations(
        [
            core.Material(
                component=entry["component"],
                destination=entry["destination"],
                ownership=entry["ownership"],
                data=b"",
            )
            for entry in files
        ]
    )
    owners = {entry["component"] for entry in files}
    if not owners <= resolved or resolved - owners:
        raise ManagedPlanError(
            "INVALID_OLD_LOCK",
            "lock file owners must be exactly the resolved component ownership set",
        )


def _intent_as_configuration(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "recipe": intent["recipe"],
        "components": {
            "include": list(intent["components"]["include"]),
            "exclude": list(intent["components"]["exclude"]),
        },
        "parameters": json.loads(json.dumps(intent["parameters"])),
    }


def _verify_source_transition(old_revision: str, new_revision: str) -> None:
    context = composer_source.GitSourceContext(core.SOURCE_ROOT)
    try:
        context.verify_descendant(old_revision, new_revision)
    except composer_source.SourceContextError as exc:
        raise ManagedPlanError(exc.code, exc.message) from exc


def _component_plan(
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
            change = {
                "id": component_id,
                "from_version": old["version"],
                "to_version": new["version"],
                "from_descriptor_sha256": old["descriptor_sha256"],
                "to_descriptor_sha256": new["descriptor_sha256"],
            }
            components["changed"].append(change)
            conflicts.append(
                _conflict(
                    "COMPONENT_VERSION_UPGRADE_REQUIRED",
                    f"component version changed for {component_id}: {old['version']} -> {new['version']}",
                    component=component_id,
                )
            )
        elif old["descriptor_sha256"] != new["descriptor_sha256"]:
            change = {
                "id": component_id,
                "from_version": old["version"],
                "to_version": new["version"],
                "from_descriptor_sha256": old["descriptor_sha256"],
                "to_descriptor_sha256": new["descriptor_sha256"],
            }
            components["changed"].append(change)
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


def _file_digest(path: Path) -> str:
    try:
        return core.sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise ManagedPlanError("READ_FAILED", f"cannot read managed destination {path}: {exc}") from exc


def _current_regular_digest(target: Path, destination: str) -> tuple[str | None, str | None]:
    path = target / destination
    if not core._parent_chain_is_safe(target, path):
        return None, "materialized path has an unsafe or symbolic-link parent"
    if path.is_symlink():
        return None, "materialized destination is a symbolic link"
    if not path.exists():
        return None, "materialized destination is missing"
    if not path.is_file():
        return None, "materialized destination is not a regular file"
    return _file_digest(path), None


def _structural_conflicts_for_new_destination(
    target: Path,
    destination: str,
    inventory: list[tuple[str, tuple[str, ...], str]],
) -> list[str]:
    planned = core._normalized_parts(destination)
    exact = target / destination
    messages: list[str] = []
    for actual_text, actual, kind in inventory:
        if actual_text in {
            core.LOCK_RELATIVE,
            core.TRANSACTION_RELATIVE,
        } or actual_text.startswith(core.STAGING_PREFIX + "/"):
            continue
        if actual == planned and actual_text != destination:
            messages.append(f"portable case collision with existing {kind}: {actual_text}")
        elif actual == planned:
            messages.append(f"destination already exists as {kind}: {actual_text}")
        elif actual == planned[: len(actual)] and len(actual) < len(planned):
            if kind != "directory":
                messages.append(f"planned parent path is existing {kind}: {actual_text}")
        elif planned == actual[: len(planned)] and len(planned) < len(actual):
            messages.append(f"planned file would contain existing path: {actual_text}")
    if exact.is_symlink() and "destination already exists as symlink" not in messages:
        messages.append("destination is a symbolic link")
    return sorted(set(messages))


def _file_plan(
    target: Path,
    old_lock: dict[str, Any],
    materials: list[core.Material],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, str]]:
    old_map = {entry["destination"]: entry for entry in old_lock["files"]}
    new_map = {material.destination: material for material in materials}
    inventory = core._existing_inventory(target)
    files: dict[str, list[dict[str, Any]]] = {
        "create": [],
        "replace": [],
        "remove": [],
        "preserve": [],
        "unchanged": [],
        "conflict": [],
    }
    conflicts: list[dict[str, Any]] = []
    carried_seed_digests: dict[str, str] = {}

    def add_conflict(destination: str, code: str, message: str, **details: Any) -> None:
        entry = {"destination": destination, "code": code, "message": message}
        entry.update(details)
        files["conflict"].append(entry)
        conflicts.append(_conflict(code, message, destination=destination, **details))

    for destination in sorted(set(old_map) | set(new_map)):
        old = old_map.get(destination)
        new = new_map.get(destination)
        if old is not None and new is not None:
            if old["component"] != new.component:
                add_conflict(
                    destination,
                    "FILE_OWNER_TRANSITION_UPGRADE_REQUIRED",
                    f"material owner changes from {old['component']} to {new.component}",
                    from_component=old["component"],
                    to_component=new.component,
                )
                continue
            if old["ownership"] != new.ownership:
                add_conflict(
                    destination,
                    "OWNERSHIP_TRANSITION_UPGRADE_REQUIRED",
                    f"ownership changes from {old['ownership']} to {new.ownership}",
                    component=new.component,
                    from_ownership=old["ownership"],
                    to_ownership=new.ownership,
                )
                continue
            current_digest, current_error = _current_regular_digest(target, destination)
            if current_error is not None:
                add_conflict(
                    destination,
                    "OLD_STATE_INVALID",
                    current_error,
                    component=old["component"],
                    ownership=old["ownership"],
                )
                continue
            if old["ownership"] == "seed":
                carried_seed_digests[destination] = old["materialized_sha256"]
                files["preserve"].append(
                    {
                        "destination": destination,
                        "component": old["component"],
                        "ownership": "seed",
                        "current_sha256": current_digest,
                        "lock_sha256": old["materialized_sha256"],
                        "reason": "consumer-owned seed",
                    }
                )
                continue
            if current_digest != old["materialized_sha256"]:
                add_conflict(
                    destination,
                    "LOCAL_MODIFICATION",
                    f"locally modified {old['ownership']} material cannot be replaced",
                    component=old["component"],
                    ownership=old["ownership"],
                    expected_sha256=old["materialized_sha256"],
                    current_sha256=current_digest,
                )
                continue
            new_digest = core.sha256_bytes(new.data)
            entry = {
                "destination": destination,
                "component": new.component,
                "ownership": new.ownership,
                "from_sha256": old["materialized_sha256"],
                "to_sha256": new_digest,
            }
            if new_digest == old["materialized_sha256"]:
                files["unchanged"].append(entry)
            else:
                files["replace"].append(entry)
            continue

        if new is not None:
            structural = _structural_conflicts_for_new_destination(target, destination, inventory)
            if structural:
                for message in structural:
                    add_conflict(
                        destination,
                        "DESTINATION_CONFLICT",
                        message,
                        component=new.component,
                        ownership=new.ownership,
                    )
                continue
            files["create"].append(
                {
                    "destination": destination,
                    "component": new.component,
                    "ownership": new.ownership,
                    "to_sha256": core.sha256_bytes(new.data),
                }
            )
            continue

        assert old is not None
        current_digest, current_error = _current_regular_digest(target, destination)
        if current_error is not None:
            add_conflict(
                destination,
                "OLD_STATE_INVALID",
                current_error,
                component=old["component"],
                ownership=old["ownership"],
            )
            continue
        if old["ownership"] == "seed":
            files["preserve"].append(
                {
                    "destination": destination,
                    "component": old["component"],
                    "ownership": "seed",
                    "current_sha256": current_digest,
                    "lock_sha256": old["materialized_sha256"],
                    "reason": "removed seed becomes consumer-owned extra file",
                }
            )
            continue
        if current_digest != old["materialized_sha256"]:
            add_conflict(
                destination,
                "LOCAL_MODIFICATION",
                f"locally modified removed {old['ownership']} material cannot be deleted",
                component=old["component"],
                ownership=old["ownership"],
                expected_sha256=old["materialized_sha256"],
                current_sha256=current_digest,
            )
            continue
        files["remove"].append(
            {
                "destination": destination,
                "component": old["component"],
                "ownership": old["ownership"],
                "from_sha256": old["materialized_sha256"],
            }
        )

    for entries in files.values():
        entries.sort(key=lambda entry: (entry["destination"], entry.get("code", "")))
    conflicts.sort(key=lambda entry: (entry.get("destination", ""), entry["code"], entry["message"]))
    return files, conflicts, carried_seed_digests


def _build_update_lock(
    old_lock: dict[str, Any],
    state: core.SourceState,
    config: dict[str, Any],
    recipe_id: str,
    selected: list[str],
    materials: list[core.Material],
    carried_seed_digests: dict[str, str],
) -> dict[str, Any]:
    synthetic_config_bytes = (
        json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    lock = core.build_lock(
        state,
        recipe_id,
        synthetic_config_bytes,
        config,
        selected,
        materials,
    )
    lock["configuration_sha256"] = old_lock["configuration_sha256"]
    for entry in lock["files"]:
        carried = carried_seed_digests.get(entry["destination"])
        if carried is not None:
            entry["materialized_sha256"] = carried
    core._schema_validate(
        core.SOURCE_ROOT / "schemas/composition-lock.schema.json",
        lock,
        label="planned update lock",
    )
    return lock


def plan_update(target: Path) -> tuple[int, dict[str, Any]]:
    state = core.load_source_state()
    old_lock = _load_old_lock(target)
    if old_lock["source"]["repository"] != core.CANONICAL_REPOSITORY:
        raise ManagedPlanError(
            "UNSUPPORTED_SOURCE_IDENTITY",
            f"unsupported composition source identity: {old_lock['source']['repository']}",
        )
    _verify_source_transition(old_lock["source"]["revision"], state.revision)

    config = _intent_as_configuration(old_lock["intent"])
    recipe, selected = core.resolve_configuration(state, config)
    materials = core.build_materials(state, selected)
    components, component_conflicts = _component_plan(old_lock, state, selected)
    files, file_conflicts, carried_seed_digests = _file_plan(target, old_lock, materials)
    lock_preview = _build_update_lock(
        old_lock,
        state,
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
        "operation": "update",
        "from_revision": old_lock["source"]["revision"],
        "to_revision": state.revision,
        "intent": old_lock["intent"],
        "recipe": {
            "id": recipe["id"],
            "from_sha256": old_lock["recipe_sha256"],
            "to_sha256": lock_preview["recipe_sha256"],
            "changed": old_lock["recipe_sha256"] != lock_preview["recipe_sha256"],
        },
        "components": components,
        "files": files,
        "conflicts": conflicts,
        "lock_preview": lock_preview,
    }
    return (0 if not conflicts else 2), payload
