#!/usr/bin/env python3
"""Deterministic composition resolver, planner, materializer, and validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SOURCE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPOSITORY = "TakashiSasaki/templates"
LOCK_RELATIVE = ".template-composition/lock.json"
TRANSACTION_RELATIVE = ".template-composition/transaction.json"
STAGING_PREFIX = ".template-composition/staging"
SUPPORTED_GENERATORS = {"contract-manifest-v1"}
SOURCE_CONSUMER_VALIDATOR = (
    SOURCE_ROOT
    / "components"
    / "lifecycle.composition-state"
    / "files"
    / ".template-composition"
    / "validate_composition.py"
)


class CompositionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class StrictJsonError(ValueError):
    pass


@dataclass(frozen=True)
class Material:
    component: str
    destination: str
    ownership: str
    data: bytes


@dataclass(frozen=True)
class SourceState:
    revision: str
    catalog: dict[str, Any]
    components: dict[str, dict[str, Any]]
    recipes: dict[str, dict[str, Any]]


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise StrictJsonError(f"non-standard JSON numeric constant {value!r}")


def load_json_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, StrictJsonError) as exc:
        raise CompositionError("INVALID_JSON", f"{label}: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CompositionError("READ_FAILED", f"cannot read {path}: {exc}") from exc
    return load_json_bytes(data, label=str(path))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_git(*arguments: str, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(SOURCE_ROOT), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise CompositionError("GIT_UNAVAILABLE", f"cannot execute git: {exc}") from exc
    if result.returncode != 0 and not allow_failure:
        raise CompositionError(
            "GIT_FAILED",
            f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
        )
    return result


def source_revision() -> str:
    revision = _run_git("rev-parse", "HEAD").stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or revision == "0" * 40:
        raise CompositionError("INVALID_SOURCE_REVISION", f"invalid source revision: {revision!r}")
    dirty = _run_git("status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        raise CompositionError(
            "DIRTY_SOURCE",
            "composition source checkout has tracked modifications; commit or discard them before composing",
        )
    return revision


def _assert_tracked_authority(path: Path) -> None:
    try:
        relative = path.relative_to(SOURCE_ROOT).as_posix()
    except ValueError as exc:
        raise CompositionError(
            "SOURCE_OUTSIDE_REPOSITORY",
            f"source authority is outside the composition checkout: {path}",
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise CompositionError(
            "INVALID_SOURCE_AUTHORITY",
            f"source authority must be a regular non-symlink file: {relative}",
        )
    tracked = _run_git("ls-files", "--error-unmatch", "--", relative, allow_failure=True)
    if tracked.returncode != 0:
        raise CompositionError(
            "UNTRACKED_SOURCE_AUTHORITY",
            f"source authority is not tracked by the bound Git revision: {relative}",
        )


def _schema_validate(schema_path: Path, value: Any, *, label: str) -> None:
    _assert_tracked_authority(schema_path)
    schema = read_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(value),
            key=lambda error: tuple(error.absolute_path),
        )
    except Exception as exc:
        raise CompositionError("INVALID_SCHEMA", f"{schema_path}: {exc}") from exc
    if errors:
        rendered = "; ".join(error.message for error in errors[:5])
        raise CompositionError("SCHEMA_VALIDATION_FAILED", f"{label}: {rendered}")


def _component_path(component_id: str) -> Path:
    return SOURCE_ROOT / "components" / component_id / "component.json"


def _recipe_path(recipe_id: str) -> Path:
    return SOURCE_ROOT / "recipes" / f"{recipe_id}.json"


def _normalized_parts(path: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path.split("/"))


def _reserved_destination(path: str) -> bool:
    parts = _normalized_parts(path)
    lock = _normalized_parts(LOCK_RELATIVE)
    transaction = _normalized_parts(TRANSACTION_RELATIVE)
    staging = _normalized_parts(STAGING_PREFIX)
    return (
        parts == lock[: len(parts)]
        or lock == parts[: len(lock)]
        or parts == transaction[: len(parts)]
        or transaction == parts[: len(transaction)]
        or parts == staging
        or staging == parts[: len(staging)]
    )


def load_source_state() -> SourceState:
    revision = source_revision()
    catalog_path = SOURCE_ROOT / "catalog/catalog.json"
    _assert_tracked_authority(catalog_path)
    catalog = read_json(catalog_path)
    _schema_validate(SOURCE_ROOT / "schemas/catalog.schema.json", catalog, label="catalog")

    component_ids = catalog["components"]
    recipe_ids = catalog["recipes"]
    if component_ids != sorted(component_ids) or len(component_ids) != len(set(component_ids)):
        raise CompositionError("INVALID_CATALOG", "catalog component IDs must be unique and lexically ordered")
    if recipe_ids != sorted(recipe_ids) or len(recipe_ids) != len(set(recipe_ids)):
        raise CompositionError("INVALID_CATALOG", "catalog recipe IDs must be unique and lexically ordered")

    actual_components = sorted(path.name for path in (SOURCE_ROOT / "components").iterdir() if path.is_dir())
    actual_recipes = sorted(path.stem for path in (SOURCE_ROOT / "recipes").glob("*.json"))
    if actual_components != component_ids:
        raise CompositionError("CATALOG_NOT_CLOSED", "catalog component inventory does not match components/")
    if actual_recipes != recipe_ids:
        raise CompositionError("CATALOG_NOT_CLOSED", "catalog recipe inventory does not match recipes/")

    components: dict[str, dict[str, Any]] = {}
    for component_id in component_ids:
        descriptor_path = _component_path(component_id)
        _assert_tracked_authority(descriptor_path)
        descriptor = read_json(descriptor_path)
        _schema_validate(SOURCE_ROOT / "schemas/component.schema.json", descriptor, label=f"component {component_id}")
        if descriptor["id"] != component_id:
            raise CompositionError("INVALID_COMPONENT", f"descriptor identity mismatch for {component_id}")
        components[component_id] = descriptor

    recipes: dict[str, dict[str, Any]] = {}
    for recipe_id in recipe_ids:
        path = _recipe_path(recipe_id)
        _assert_tracked_authority(path)
        recipe = read_json(path)
        _schema_validate(SOURCE_ROOT / "schemas/recipe.schema.json", recipe, label=f"recipe {recipe_id}")
        if recipe["id"] != recipe_id:
            raise CompositionError("INVALID_RECIPE", f"recipe identity mismatch for {recipe_id}")
        recipes[recipe_id] = recipe

    _validate_source_graph(components, recipes)
    return SourceState(revision, catalog, components, recipes)


def _validate_source_graph(components: dict[str, dict[str, Any]], recipes: dict[str, dict[str, Any]]) -> None:
    ids = set(components)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visited:
            return
        if component_id in visiting:
            raise CompositionError("DEPENDENCY_CYCLE", f"component dependency cycle at {component_id}")
        visiting.add(component_id)
        descriptor = components[component_id]
        if component_id in descriptor["requires"] or component_id in descriptor["conflicts"]:
            raise CompositionError("INVALID_COMPONENT", f"{component_id} references itself")
        overlap = set(descriptor["requires"]) & set(descriptor["conflicts"])
        if overlap:
            raise CompositionError("INVALID_COMPONENT", f"{component_id} both requires and conflicts with {sorted(overlap)}")
        for reference in descriptor["requires"] + descriptor["conflicts"]:
            if reference not in ids:
                raise CompositionError("UNKNOWN_COMPONENT", f"{component_id} references missing component {reference}")
        if descriptor["kind"] in {"capability", "lifecycle"} and any(
            reference.startswith("artifact.")
            for reference in descriptor["requires"] + descriptor["conflicts"]
        ):
            raise CompositionError(
                "GENERIC_ARTIFACT_DEPENDENCY",
                f"generic component {component_id} references an artifact component",
            )
        for dependency in descriptor["requires"]:
            visit(dependency)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in sorted(components):
        visit(component_id)

    for recipe_id, recipe in recipes.items():
        artifact = recipe["artifact"]
        if artifact not in components or components[artifact]["kind"] != "artifact":
            raise CompositionError("INVALID_RECIPE", f"recipe {recipe_id} has unknown artifact {artifact}")
        groups = [
            set(recipe["required_components"]),
            set(recipe["default_components"]),
            set(recipe["optional_components"]),
        ]
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise CompositionError("INVALID_RECIPE", f"recipe {recipe_id} selection classes overlap")
        for component_id in set().union(*groups):
            if component_id not in components or components[component_id]["kind"] == "artifact":
                raise CompositionError(
                    "INVALID_RECIPE",
                    f"recipe {recipe_id} references invalid selectable component {component_id}",
                )


def resolve_configuration(state: SourceState, config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    _schema_validate(
        SOURCE_ROOT / "schemas/composition-config.schema.json",
        config,
        label="composition configuration",
    )
    recipe_id = config["recipe"]
    recipe = state.recipes.get(recipe_id)
    if recipe is None:
        raise CompositionError("UNKNOWN_RECIPE", f"unknown production recipe: {recipe_id}")

    required = set(recipe["required_components"])
    defaults = set(recipe["default_components"])
    optional = set(recipe["optional_components"])
    exposed = required | defaults | optional
    include = set(config["components"]["include"])
    exclude = set(config["components"]["exclude"])
    if include & exclude:
        raise CompositionError("SELECTION_OVERLAP", f"include/exclude overlap: {sorted(include & exclude)}")
    unknown_include = include - exposed
    unknown_exclude = exclude - exposed
    if unknown_include:
        raise CompositionError(
            "COMPONENT_NOT_EXPOSED",
            f"recipe {recipe_id} does not expose included components: {sorted(unknown_include)}",
        )
    if unknown_exclude:
        raise CompositionError(
            "COMPONENT_NOT_EXPOSED",
            f"recipe {recipe_id} does not expose excluded components: {sorted(unknown_exclude)}",
        )
    required_excluded = required & exclude
    if required_excluded:
        raise CompositionError(
            "REQUIRED_COMPONENT_EXCLUDED",
            f"cannot exclude recipe-required components: {sorted(required_excluded)}",
        )

    selected = {recipe["artifact"], *required, *(defaults - exclude), *include}
    queue = list(selected)
    while queue:
        component_id = queue.pop()
        for dependency in state.components[component_id]["requires"]:
            if dependency not in selected:
                selected.add(dependency)
                queue.append(dependency)

    excluded_dependencies = selected & exclude
    if excluded_dependencies:
        raise CompositionError(
            "EXCLUDED_DEPENDENCY",
            "excluded components are required by the resolved closure: " f"{sorted(excluded_dependencies)}",
        )
    for component_id in sorted(selected):
        active_conflicts = set(state.components[component_id]["conflicts"]) & selected
        if active_conflicts:
            raise CompositionError(
                "COMPONENT_CONFLICT",
                f"{component_id} conflicts with selected components {sorted(active_conflicts)}",
            )
    unresolved_parameters = set(config.get("parameters", {})) - selected
    if unresolved_parameters:
        raise CompositionError(
            "PARAMETER_COMPONENT_UNRESOLVED",
            f"parameters target unresolved components: {sorted(unresolved_parameters)}",
        )
    return recipe, sorted(selected)


def _render_contract_manifest(state: SourceState, selected: list[str]) -> bytes:
    registrations: list[dict[str, Any]] = []
    ids: set[str] = set()
    documents: set[str] = set()
    schemas: set[str] = set()
    for component_id in selected:
        for registration in state.components[component_id].get("contract_registrations", []):
            if registration["id"] in ids:
                raise CompositionError("DUPLICATE_CONTRACT_REGISTRATION", f"duplicate contract id: {registration['id']}")
            if registration["document"] in documents:
                raise CompositionError(
                    "DUPLICATE_CONTRACT_REGISTRATION",
                    f"duplicate contract document: {registration['document']}",
                )
            if registration["schema"] in schemas:
                raise CompositionError(
                    "DUPLICATE_CONTRACT_REGISTRATION",
                    f"duplicate contract schema: {registration['schema']}",
                )
            ids.add(registration["id"])
            documents.add(registration["document"])
            schemas.add(registration["schema"])
            history = []
            for source_entry in registration["version_history"]:
                rendered = {"version": source_entry["version"], "changeType": source_entry["change_type"]}
                if "migration" in source_entry:
                    rendered["migration"] = source_entry["migration"]
                history.append(rendered)
            registrations.append(
                {
                    "id": registration["id"],
                    "document": registration["document"],
                    "schema": registration["schema"],
                    "migrationSlug": registration["migration_slug"],
                    "documentSchemaVersion": registration["document_schema_version"],
                    "versionHistory": history,
                    "purpose": registration["purpose"],
                }
            )
    registrations.sort(key=lambda entry: entry["id"])
    manifest = {
        "$schema": "../schemas/contract-manifest.schema.json",
        "schemaVersion": 1,
        "versionHistory": [{"version": 1, "changeType": "initial"}],
        "contracts": registrations,
        "retiredContracts": [],
    }
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_materials(state: SourceState, selected: list[str]) -> list[Material]:
    materials: list[Material] = []
    for component_id in selected:
        descriptor = state.components[component_id]
        component_root = _component_path(component_id).parent
        for declaration in descriptor["materials"]:
            if "source" in declaration:
                source = component_root / declaration["source"]
                _assert_tracked_authority(source)
                try:
                    data = source.read_bytes()
                except OSError as exc:
                    raise CompositionError("READ_FAILED", f"cannot read source material {source}: {exc}") from exc
            else:
                generator = declaration["generator"]
                if generator not in SUPPORTED_GENERATORS:
                    raise CompositionError("UNKNOWN_GENERATOR", f"unsupported generated material handler: {generator}")
                if generator == "contract-manifest-v1":
                    data = _render_contract_manifest(state, selected)
                else:
                    raise AssertionError(generator)
            materials.append(
                Material(
                    component=component_id,
                    destination=declaration["destination"],
                    ownership=declaration["ownership"],
                    data=data,
                )
            )
    _validate_material_destinations(materials)
    return sorted(materials, key=lambda material: material.destination)


def _validate_material_destinations(materials: list[Material]) -> None:
    normalized: list[tuple[Material, tuple[str, ...]]] = []
    for material in materials:
        if _reserved_destination(material.destination):
            raise CompositionError(
                "RESERVED_DESTINATION",
                f"material conflicts with reserved composer metadata: {material.destination}",
            )
        normalized.append((material, _normalized_parts(material.destination)))
    for index, (left_material, left) in enumerate(normalized):
        for right_material, right in normalized[index + 1 :]:
            if left == right:
                raise CompositionError(
                    "DESTINATION_COLLISION",
                    f"material destinations collide: {left_material.destination}, {right_material.destination}",
                )
            if left == right[: len(left)] or right == left[: len(right)]:
                raise CompositionError(
                    "DESTINATION_COLLISION",
                    f"material file/directory paths conflict: {left_material.destination}, {right_material.destination}",
                )


def _existing_inventory(target: Path) -> list[tuple[str, tuple[str, ...], str]]:
    if not target.exists():
        return []
    inventory: list[tuple[str, tuple[str, ...], str]] = []
    for root, dirs, files in os.walk(target, topdown=True, followlinks=False):
        root_path = Path(root)
        original_dirs = list(dirs)
        dirs[:] = [
            name
            for name in original_dirs
            if name.casefold() != ".git" and not (root_path / name).is_symlink()
        ]
        for name in original_dirs + list(files):
            if name.casefold() == ".git" and root_path == target:
                continue
            path = root_path / name
            relative = path.relative_to(target).as_posix()
            if path.is_symlink():
                kind = "symlink"
            elif path.is_dir():
                kind = "directory"
            else:
                kind = "file"
            inventory.append((relative, _normalized_parts(relative), kind))
    return inventory


def plan_target(target: Path, materials: list[Material]) -> tuple[list[dict[str, str]], list[str]]:
    actions: list[dict[str, str]] = []
    conflicts: list[str] = []
    if target.exists() and target.is_symlink():
        return actions, ["consumer repository root must not be a symbolic link"]
    lock_path = target / LOCK_RELATIVE
    if lock_path.exists() or lock_path.is_symlink():
        return actions, [
            "INITIAL_MODE_REQUIRES_UNMANAGED_TARGET: target already contains a composition lock; "
            "use --mode update to preserve locked intent, or --mode upgrade with an explicit "
            "configuration to change intent or compatibility boundaries"
        ]
    for reserved in (TRANSACTION_RELATIVE, STAGING_PREFIX):
        path = target / reserved
        if path.exists() or path.is_symlink():
            return actions, [f"reserved composer metadata already exists: {reserved}"]
    existing = _existing_inventory(target)

    for material in materials:
        planned = _normalized_parts(material.destination)
        exact = target / material.destination
        material_conflicts: list[str] = []
        for actual_text, actual, kind in existing:
            if actual == planned and actual_text != material.destination:
                material_conflicts.append(f"portable case collision with existing {kind}: {actual_text}")
            elif actual == planned:
                continue
            elif actual == planned[: len(actual)] and len(actual) < len(planned):
                if kind != "directory":
                    material_conflicts.append(f"planned parent path is existing {kind}: {actual_text}")
            elif planned == actual[: len(planned)] and len(planned) < len(actual):
                material_conflicts.append(f"planned file would contain existing path: {actual_text}")

        if exact.is_symlink():
            material_conflicts.append("destination is a symbolic link")
        elif exact.exists():
            if not exact.is_file():
                material_conflicts.append("destination exists and is not a regular file")
            else:
                try:
                    current = exact.read_bytes()
                except OSError as exc:
                    material_conflicts.append(f"cannot read existing destination: {exc}")
                else:
                    if current == material.data:
                        actions.append(
                            {
                                "destination": material.destination,
                                "component": material.component,
                                "ownership": material.ownership,
                                "action": "adopt-identical",
                            }
                        )
                    else:
                        material_conflicts.append("destination exists with different bytes")
        else:
            actions.append(
                {
                    "destination": material.destination,
                    "component": material.component,
                    "ownership": material.ownership,
                    "action": "create",
                }
            )
        for conflict in material_conflicts:
            conflicts.append(f"{material.destination}: {conflict}")
    return sorted(actions, key=lambda entry: entry["destination"]), sorted(set(conflicts))


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def normalize_intent(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "recipe": config["recipe"],
        "components": {
            "include": sorted(config["components"]["include"]),
            "exclude": sorted(config["components"]["exclude"]),
        },
        "parameters": _normalize_json(config.get("parameters", {})),
    }


def build_lock(
    state: SourceState,
    recipe_id: str,
    config_bytes: bytes,
    config: dict[str, Any],
    selected: list[str],
    materials: list[Material],
) -> dict[str, Any]:
    resolved = []
    for component_id in selected:
        descriptor_path = _component_path(component_id)
        _assert_tracked_authority(descriptor_path)
        resolved.append(
            {
                "id": component_id,
                "version": state.components[component_id]["version"],
                "descriptor_sha256": sha256_bytes(descriptor_path.read_bytes()),
            }
        )
    recipe_path = _recipe_path(recipe_id)
    _assert_tracked_authority(recipe_path)
    files = [
        {
            "destination": material.destination,
            "component": material.component,
            "ownership": material.ownership,
            "materialized_sha256": sha256_bytes(material.data),
        }
        for material in materials
    ]
    lock = {
        "schema_version": 2,
        "source": {"repository": CANONICAL_REPOSITORY, "revision": state.revision},
        "intent": normalize_intent(config),
        "recipe_sha256": sha256_bytes(recipe_path.read_bytes()),
        "configuration_sha256": sha256_bytes(config_bytes),
        "resolved_components": sorted(resolved, key=lambda entry: entry["id"]),
        "files": sorted(files, key=lambda entry: entry["destination"]),
    }
    _schema_validate(
        SOURCE_ROOT / "schemas/composition-lock.schema.json",
        lock,
        label="generated composition lock",
    )
    return lock


def _parent_chain_is_safe(target: Path, destination: Path) -> bool:
    try:
        relative = destination.parent.relative_to(target)
    except ValueError:
        return False
    candidate = target
    if candidate.exists() and candidate.is_symlink():
        return False
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            return False
        if candidate.exists() and not candidate.is_dir():
            return False
    return True


def _write_no_overwrite(target: Path, destination: Path, data: bytes) -> None:
    if not _parent_chain_is_safe(target, destination):
        raise CompositionError("WRITE_CONFLICT", f"unsafe parent path while applying {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not _parent_chain_is_safe(target, destination):
        raise CompositionError("WRITE_CONFLICT", f"parent path changed unsafely while applying {destination}")
    if destination.is_symlink():
        raise CompositionError("WRITE_CONFLICT", f"refusing to replace symlink: {destination}")

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".template-composition-tmp-",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_name, destination)
        except FileExistsError as exc:
            raise CompositionError("WRITE_CONFLICT", f"destination appeared during apply: {destination}") from exc
        except OSError as exc:
            raise CompositionError("WRITE_FAILED", f"cannot install {destination}: {exc}") from exc
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def apply_plan(target: Path, actions: list[dict[str, str]], materials: list[Material], lock: dict[str, Any]) -> None:
    if target.exists() and target.is_symlink():
        raise CompositionError("INVALID_TARGET", "consumer repository root must not be a symbolic link")
    target.mkdir(parents=True, exist_ok=True)
    material_by_destination = {material.destination: material for material in materials}
    for action in actions:
        if action["action"] != "create":
            continue
        material = material_by_destination[action["destination"]]
        _write_no_overwrite(target, target / material.destination, material.data)
    lock_bytes = (json.dumps(lock, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_no_overwrite(target, target / LOCK_RELATIVE, lock_bytes)


def validate_consumer_with_source_validator(target: Path) -> tuple[bool, list[str]]:
    _assert_tracked_authority(SOURCE_CONSUMER_VALIDATOR)
    result = subprocess.run(
        [sys.executable, str(SOURCE_CONSUMER_VALIDATOR), str(target)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return True, []
    errors = [line.removeprefix("ERROR: ") for line in result.stderr.splitlines() if line.strip()]
    if not errors:
        errors = [result.stdout.strip() or f"source validator exited with status {result.returncode}"]
    return False, errors


def load_configuration(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CompositionError("READ_FAILED", f"cannot read configuration {path}: {exc}") from exc
    value = load_json_bytes(data, label=str(path))
    if not isinstance(value, dict):
        raise CompositionError("INVALID_CONFIG", "composition configuration must be an object")
    return data, value


def _has_materialized_composition_material(target: Path) -> bool:
    """Detect reserved Composition files that are not backed by a consumer lock."""
    metadata = target / ".template-composition"
    if metadata.is_symlink() or not metadata.is_dir():
        return False
    for relative in ("validate.py", "validate_composition.py", "validators"):
        candidate = metadata / relative
        if candidate.is_symlink() or candidate.is_file() or candidate.is_dir():
            return True
    return False


def _inspect_guidance(state: str) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "current_state": state,
        "normal_consumer_entrypoint": (
            "python scripts/run.py --repository <root> <operation>"
        ),
        "recovery_required": state == "managed-interrupted",
    }
    if state in {"absent", "unmanaged"}:
        guidance.update(
            {
                "relevant_mode": "initial",
                "allowed_next_operations": [
                    "inspect",
                    "plan --config composition.json",
                    "apply --config composition.json",
                ],
            }
        )
    elif state == "managed-valid":
        guidance.update(
            {
                "relevant_mode": "managed",
                "allowed_next_operations": [
                    "inspect",
                    "validate",
                    "plan --mode update",
                    "plan --mode upgrade --config composition.json",
                ],
            }
        )
    elif state == "managed-interrupted":
        guidance.update(
            {
                "relevant_mode": "recovery",
                "allowed_next_operations": [
                    "inspect",
                    "apply --mode update",
                    "apply --mode upgrade",
                ],
            }
        )
    else:
        guidance.update(
            {
                "relevant_mode": "repair",
                "allowed_next_operations": ["inspect"],
            }
        )
    return guidance


def _inspect_payload(
    state: str, target: Path, **fields: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "state": state,
        "target": str(target),
        "guidance": _inspect_guidance(state),
    }
    payload.update(fields)
    return payload


def command_inspect(target: Path) -> tuple[int, dict[str, Any]]:
    if not target.exists():
        return 0, _inspect_payload("absent", target)
    if target.is_symlink():
        return 2, _inspect_payload(
            "invalid",
            target,
            errors=["target root is a symbolic link"],
        )
    transaction = target / TRANSACTION_RELATIVE
    if transaction.exists() or transaction.is_symlink():
        return 2, _inspect_payload(
            "managed-interrupted",
            target,
            errors=[
                "composition transaction is present; recovery required: "
                f"{TRANSACTION_RELATIVE}"
            ],
        )
    lock_path = target / LOCK_RELATIVE
    if not lock_path.exists() and not lock_path.is_symlink():
        if _has_materialized_composition_material(target):
            return 2, _inspect_payload(
                "unmanaged-materialized",
                target,
                code="NOT_A_MANAGED_CONSUMER_ENTRYPOINT",
                message=(
                    "Composition material exists without a consumer lock. "
                    "Do not execute materialized .template-composition files directly; "
                    "use the installed Composition skill runner for initial composition."
                ),
                errors=[
                    "normal consumer entrypoint is the installed Composition skill runner; "
                    "materialized Composition files require a managed lock"
                ],
            )
        return 0, _inspect_payload("unmanaged", target)
    try:
        valid, errors = validate_consumer_with_source_validator(target)
    except CompositionError as exc:
        return 2, _inspect_payload(
            "managed-invalid",
            target,
            errors=[exc.message],
        )
    return (
        0 if valid else 2,
        _inspect_payload(
            "managed-valid" if valid else "managed-invalid",
            target,
            errors=errors,
        ),
    )

def command_plan(config_path: Path, target: Path) -> tuple[int, dict[str, Any]]:
    state = load_source_state()
    config_bytes, config = load_configuration(config_path)
    recipe, selected = resolve_configuration(state, config)
    materials = build_materials(state, selected)
    actions, conflicts = plan_target(target, materials)
    lock = build_lock(state, recipe["id"], config_bytes, config, selected, materials)
    payload = {
        "schema_version": 2,
        "operation": "initial",
        "source": {"repository": CANONICAL_REPOSITORY, "revision": state.revision},
        "intent": normalize_intent(config),
        "configuration_sha256": sha256_bytes(config_bytes),
        "resolved_components": selected,
        "actions": actions,
        "conflicts": conflicts,
        "lock_preview": lock,
    }
    return (0 if not conflicts else 2), payload


def command_apply(config_path: Path, target: Path) -> tuple[int, dict[str, Any]]:
    state = load_source_state()
    config_bytes, config = load_configuration(config_path)
    recipe, selected = resolve_configuration(state, config)
    materials = build_materials(state, selected)
    actions, conflicts = plan_target(target, materials)
    if conflicts:
        return 2, {
            "status": "conflict",
            "operation": "initial",
            "target": str(target),
            "recipe": recipe["id"],
            "conflicts": conflicts,
        }
    lock = build_lock(state, recipe["id"], config_bytes, config, selected, materials)
    apply_plan(target, actions, materials, lock)
    valid, errors = validate_consumer_with_source_validator(target)
    if not valid:
        try:
            (target / LOCK_RELATIVE).unlink()
        except OSError:
            pass
        return 3, {"status": "validation-failed", "target": str(target), "errors": errors}
    return 0, {
        "status": "applied",
        "operation": "initial",
        "target": str(target),
        "recipe": recipe["id"],
        "resolved_components": selected,
        "created": [entry["destination"] for entry in actions if entry["action"] == "create"],
        "adopted": [entry["destination"] for entry in actions if entry["action"] == "adopt-identical"],
        "lock": LOCK_RELATIVE,
    }


def command_validate(target: Path) -> tuple[int, dict[str, Any]]:
    try:
        valid, errors = validate_consumer_with_source_validator(target)
    except CompositionError as exc:
        return 2, {"status": "invalid", "target": str(target), "errors": [exc.message]}
    return (
        0 if valid else 2,
        {"status": "valid" if valid else "invalid", "target": str(target), "errors": errors},
    )


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--target", required=True, type=Path)

    for name in ("plan", "apply"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--config", required=True, type=Path)
        subparser.add_argument("--target", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--target", required=True, type=Path)

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            status, payload = command_inspect(args.target.absolute())
        elif args.command == "plan":
            status, payload = command_plan(args.config.absolute(), args.target.absolute())
        elif args.command == "apply":
            status, payload = command_apply(args.config.absolute(), args.target.absolute())
        elif args.command == "validate":
            status, payload = command_validate(args.target.absolute())
        else:
            raise AssertionError(args.command)
    except CompositionError as exc:
        _emit({"status": "error", "code": exc.code, "message": exc.message})
        return 2
    _emit(payload)
    return status
