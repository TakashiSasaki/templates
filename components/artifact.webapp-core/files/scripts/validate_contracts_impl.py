#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import copy
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
MANIFEST_PATH = "contracts/manifest.json"
MANIFEST_SCHEMA_PATH = "schemas/contract-manifest.schema.json"
VISUALLY_BLANK_CHARACTERS = {"\u2800", "\U00013441", "\U00013442", "\U0001D159"}
ROOT = Path(__file__).resolve().parents[1]


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains the same member name more than once."""


class NonStandardJsonConstantError(ValueError):
    """Raised when JSON text contains NaN or an infinity constant."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> Any:
    raise NonStandardJsonConstantError(f"non-standard JSON numeric constant {value!r}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )


def load_contract_manifest(root: Path) -> dict[str, Any]:
    manifest = load_json(root / MANIFEST_PATH)
    if not isinstance(manifest, dict):
        raise TypeError("contract manifest must be a JSON object")
    return manifest


def registry_from_manifest(
    manifest: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    return {
        entry["id"]: (entry["document"], entry["schema"])
        for entry in manifest["contracts"]
    }


def load_contract_registry(root: Path) -> dict[str, tuple[str, str]]:
    return registry_from_manifest(load_contract_manifest(root))


def _bootstrap_contract_registry() -> dict[str, tuple[str, str]]:
    try:
        return load_contract_registry(ROOT)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateKeyError,
        NonStandardJsonConstantError,
        TypeError,
        KeyError,
    ):
        return {}


CONTRACT_SCHEMAS = _bootstrap_contract_registry()


def load_contract_documents(root: Path) -> dict[str, Any]:
    return {
        name: load_json(root / contract_path)
        for name, (contract_path, _) in load_contract_registry(root).items()
    }


def _json_path(parts: list[Any]) -> str:
    if not parts:
        return "$"
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


def _duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _has_visible_character(value: str) -> bool:
    """Return whether text contains a visible base character."""

    return any(
        character not in VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def _surface_dependency_cycles(surfaces: list[dict[str, Any]]) -> list[list[str]]:
    graph = {surface["id"]: surface["surfaceDependencies"] for surface in surfaces}
    visited: set[str] = set()
    cycles: list[list[str]] = []

    for root in graph:
        if root in visited:
            continue

        path: list[str] = []
        active_index: dict[str, int] = {}
        stack: list[tuple[str, int]] = [(root, 0)]

        while stack:
            node, dependency_index = stack[-1]

            if node not in active_index:
                active_index[node] = len(path)
                path.append(node)

            dependencies = graph[node]
            if dependency_index >= len(dependencies):
                stack.pop()
                active_index.pop(node)
                path.pop()
                visited.add(node)
                continue

            dependency = dependencies[dependency_index]
            stack[-1] = (node, dependency_index + 1)

            if dependency not in graph or dependency in visited:
                continue
            if dependency in active_index:
                start = active_index[dependency]
                cycles.append(path[start:] + [dependency])
                continue

            stack.append((dependency, 0))

    return cycles


def _repository_relative_json_files(directory: Path, root: Path, pattern: str) -> set[str]:
    if not directory.is_dir():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in directory.rglob(pattern)
        if path.is_file() or path.is_symlink()
    }


def validate_contract_manifest(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = manifest["contracts"]
    ids = [entry["id"] for entry in entries]
    documents = [entry["document"] for entry in entries]
    schemas = [entry["schema"] for entry in entries]

    for label, values in (
        ("contract id", ids),
        ("contract document", documents),
        ("contract schema", schemas),
    ):
        for duplicate in sorted(_duplicate_values(values)):
            errors.append(f"duplicate {label}: {duplicate}")

    for entry in entries:
        contract_id = entry["id"]
        if not _has_visible_character(entry["purpose"]):
            errors.append(
                f"contract manifest {contract_id}: purpose must contain at least one visible character"
            )

        for label, relative in (
            ("document", entry["document"]),
            ("schema", entry["schema"]),
        ):
            candidate = root / relative
            try:
                candidate.resolve(strict=False).relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"contract manifest {contract_id}: {label} escapes repository root: {relative}"
                )
                continue
            if candidate.is_symlink():
                errors.append(
                    f"contract manifest {contract_id}: {label} must not be a symbolic link: {relative}"
                )
            elif not candidate.is_file():
                errors.append(
                    f"contract manifest {contract_id}: missing {label}: {relative}"
                )

        if entry["document"] == MANIFEST_PATH:
            errors.append(
                f"contract manifest {contract_id}: manifest must not register itself as a domain contract"
            )
        if entry["schema"] == MANIFEST_SCHEMA_PATH:
            errors.append(
                f"contract manifest {contract_id}: manifest schema must not be registered as a domain schema"
            )

    actual_documents = _repository_relative_json_files(
        root / "contracts", root, "*.json"
    ) - {MANIFEST_PATH}
    actual_schemas = _repository_relative_json_files(
        root / "schemas", root, "*.schema.json"
    ) - {MANIFEST_SCHEMA_PATH}

    for relative in sorted(actual_documents - set(documents)):
        errors.append(f"unregistered contract document: {relative}")
    for relative in sorted(actual_schemas - set(schemas)):
        errors.append(f"unregistered contract schema: {relative}")

    return errors


def cross_validate(documents: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    surfaces = documents["surfaces"]["surfaces"]
    routes = documents["routes"]["routes"]
    states = documents["ui_states"]["states"]
    viewports = documents["viewports"]["viewports"]

    surface_ids = [surface["id"] for surface in surfaces]
    route_ids = [route["id"] for route in routes]
    state_ids = [state["id"] for state in states]
    viewport_ids = [viewport["id"] for viewport in viewports]

    for label, values in (
        ("surface", surface_ids),
        ("route", route_ids),
        ("UI state", state_ids),
        ("viewport", viewport_ids),
    ):
        for duplicate in sorted(_duplicate_values(values)):
            errors.append(f"duplicate {label} id: {duplicate}")

    known_surfaces = set(surface_ids)
    known_routes = set(route_ids)
    known_states = set(state_ids)
    states_by_id = {state["id"]: state for state in states}
    routes_by_id: dict[str, dict[str, Any]] = {}
    for route in routes:
        routes_by_id.setdefault(route["id"], route)
    state_scopes_by_id: dict[str, set[str]] = {}
    for state in states:
        state_scopes_by_id.setdefault(state["id"], set()).add(state["scope"])

    for surface in surfaces:
        surface_id = surface["id"]
        for field_name in ("title", "purpose"):
            if not _has_visible_character(surface[field_name]):
                errors.append(
                    f"surface {surface_id}: {field_name} must contain at least one visible character"
                )
        authorization = surface["authorization"]
        authorization_mode = authorization["mode"]
        authentication = surface["authentication"]
        if authorization_mode == "role" and not authorization["roles"]:
            errors.append(
                f"surface {surface_id}: role authorization requires at least one role"
            )
        if authorization_mode in {"public", "authenticated"} and authorization["roles"]:
            errors.append(
                f"surface {surface_id}: {authorization_mode} authorization must not declare roles"
            )
        if authorization_mode == "public" and authentication == "required":
            errors.append(
                f"surface {surface_id}: public authorization must not require authentication"
            )
        if authorization_mode in {"authenticated", "role"} and authentication != "required":
            errors.append(
                f"surface {surface_id}: {authorization_mode} authorization requires authentication required"
            )
        if authentication == "required" and "anonymous" in surface["audiences"]:
            errors.append(
                f"surface {surface_id}: required authentication must not include anonymous audience"
            )
        for dependency in surface["surfaceDependencies"]:
            if dependency not in known_surfaces:
                errors.append(
                    f"surface {surface_id}: unknown surface dependency {dependency}"
                )
            if dependency == surface_id:
                errors.append(f"surface {surface_id}: must not depend on itself")

    for cycle in _surface_dependency_cycles(surfaces):
        errors.append(f"surface dependency cycle: {' -> '.join(cycle)}")

    for state in states:
        state_id = state["id"]
        for field_name in ("description", "focusStrategy"):
            if not _has_visible_character(state[field_name]):
                errors.append(
                    f"UI state {state_id}: {field_name} must contain at least one visible character"
                )

    route_paths: list[str] = []
    aliases: list[str] = []
    surfaces_by_id = {surface["id"]: surface for surface in surfaces}
    routed_surface_ids: set[str] = set()
    routed_state_ids: set[str] = set()
    for route in routes:
        route_id = route["id"]
        route_paths.append(route["path"])
        aliases.extend(route["aliases"])
        if not _has_visible_character(route["accessibility"]["focusTarget"]):
            errors.append(
                f"route {route_id}: focusTarget must contain at least one visible character"
            )

        surface: dict[str, Any] | None = None
        if route["surface"] not in known_surfaces:
            errors.append(f"route {route_id}: unknown surface {route['surface']}")
        else:
            surface = surfaces_by_id[route["surface"]]
            if route["canonical"]:
                routed_surface_ids.add(surface["id"])
            if route["authentication"] != surface["authentication"]:
                errors.append(
                    f"route {route_id}: authentication {route['authentication']} does not match "
                    f"surface {surface['id']} ({surface['authentication']})"
                )

        access_failures = route["accessFailures"]
        unauthenticated = access_failures["unauthenticated"]
        forbidden = access_failures["forbidden"]
        unauthenticated_behavior = unauthenticated["behavior"]
        forbidden_behavior = forbidden["behavior"]

        if route["authentication"] == "required":
            if unauthenticated_behavior not in {"render-state", "redirect"}:
                errors.append(
                    f"route {route_id}: required authentication must declare "
                    "unauthenticated access failure as render-state or redirect"
                )
        elif unauthenticated_behavior != "not-applicable":
            errors.append(
                f"route {route_id}: {route['authentication']} authentication requires "
                "unauthenticated access failure not-applicable"
            )

        if surface is not None:
            authorization_mode = surface["authorization"]["mode"]
            if authorization_mode == "role":
                if forbidden_behavior not in {"render-state", "redirect"}:
                    errors.append(
                        f"route {route_id}: role authorization must declare "
                        "forbidden access failure as render-state or redirect"
                    )
            elif forbidden_behavior != "not-applicable":
                errors.append(
                    f"route {route_id}: {authorization_mode} authorization requires "
                    "forbidden access failure not-applicable"
                )

        route_state_ids = set(route["states"])
        for condition, failure in (
            ("unauthenticated", unauthenticated),
            ("forbidden", forbidden),
        ):
            behavior = failure["behavior"]
            if behavior == "render-state":
                state_id = failure["stateId"]
                if state_id not in known_states:
                    errors.append(
                        f"route {route_id}: {condition} access failure references "
                        f"unknown UI state {state_id}"
                    )
                else:
                    state = states_by_id[state_id]
                    if state["scope"] != "route":
                        errors.append(
                            f"route {route_id}: {condition} access failure UI state "
                            f"{state_id} must be route-scoped"
                        )
                    if state["category"] != "access":
                        errors.append(
                            f"route {route_id}: {condition} access failure UI state "
                            f"{state_id} must have category access"
                        )
                if state_id not in route_state_ids:
                    errors.append(
                        f"route {route_id}: {condition} access failure render-state "
                        f"target {state_id} must be declared by the route"
                    )
            elif behavior == "redirect":
                target_id = failure["routeId"]
                if target_id not in known_routes:
                    errors.append(
                        f"route {route_id}: {condition} access failure references "
                        f"unknown redirect route {target_id}"
                    )
                elif target_id == route_id:
                    errors.append(
                        f"route {route_id}: {condition} access failure must not redirect "
                        "to the same route"
                    )
                elif (
                    condition == "unauthenticated"
                    and routes_by_id[target_id]["authentication"] == "required"
                ):
                    errors.append(
                        f"route {route_id}: unauthenticated redirect target {target_id} "
                        "must not require authentication"
                    )

        for state_id in route["states"]:
            if state_id not in known_states:
                errors.append(f"route {route_id}: unknown UI state {state_id}")
                continue
            routed_state_ids.add(state_id)
            if "global" in state_scopes_by_id[state_id]:
                errors.append(
                    f"route {route_id}: global UI state {state_id} must not be declared by a route"
                )
        if route["path"] in route["aliases"]:
            errors.append(
                f"route {route_id}: canonical path is also listed as an alias"
            )

    for surface_id in surface_ids:
        if surface_id not in routed_surface_ids:
            errors.append(
                f"surface {surface_id}: no canonical route declares this surface"
            )

    for state in states:
        if state["scope"] == "route" and state["id"] not in routed_state_ids:
            errors.append(
                f"UI state {state['id']}: route-scoped state is not declared by any route"
            )

    for duplicate in sorted(_duplicate_values(route_paths)):
        errors.append(f"duplicate canonical route path: {duplicate}")
    for duplicate in sorted(_duplicate_values(aliases)):
        errors.append(f"duplicate route alias: {duplicate}")
    for collision in sorted(set(route_paths) & set(aliases)):
        errors.append(f"route path is both canonical and alias: {collision}")

    for viewport in viewports:
        if not _has_visible_character(viewport["description"]):
            errors.append(
                f"viewport {viewport['id']}: description must contain at least one visible character"
            )

    if viewports:
        first_minimum = viewports[0]["minWidthPx"]
        if first_minimum != 0:
            errors.append("viewport coverage must start at 0px")
        for previous, current in zip(viewports, viewports[1:]):
            previous_minimum = previous["minWidthPx"]
            current_minimum = current["minWidthPx"]
            if current_minimum <= previous_minimum:
                errors.append(
                    "viewport breakpoints must be strictly increasing: "
                    f"{previous['id']}={previous_minimum}px, {current['id']}={current_minimum}px"
                )

    return errors


def _load_json_error_types() -> tuple[type[BaseException], ...]:
    return (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateKeyError,
        NonStandardJsonConstantError,
        TypeError,
        KeyError,
    )


def _validate_schema(
    root: Path,
    schema_path: str,
    errors: list[str],
) -> dict[str, Any] | None:
    try:
        schema = load_json(root / schema_path)
    except _load_json_error_types() as exc:
        errors.append(f"{schema_path}: unable to load JSON: {exc}")
        return None

    declared_dialect = schema.get("$schema") if isinstance(schema, dict) else None
    if declared_dialect != SCHEMA_DIALECT:
        errors.append(
            f"{schema_path}: unsupported JSON Schema dialect: "
            f"expected {SCHEMA_DIALECT!r}, got {declared_dialect!r}"
        )
        return None

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        errors.append(f"{schema_path}: invalid JSON Schema: {exc.message}")
        return None

    return schema


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []

    try:
        manifest = load_contract_manifest(root)
    except _load_json_error_types() as exc:
        errors.append(f"{MANIFEST_PATH}: unable to load JSON: {exc}")
        return errors

    manifest_schema = _validate_schema(root, MANIFEST_SCHEMA_PATH, errors)
    if manifest_schema is None:
        return errors

    try:
        manifest_errors = sorted(
            Draft202012Validator(manifest_schema).iter_errors(manifest),
            key=lambda item: _json_path(list(item.absolute_path)),
        )
    except Unresolvable as exc:
        errors.append(
            f"{MANIFEST_SCHEMA_PATH}: unresolved JSON Schema reference: {exc}"
        )
        return errors

    for error in manifest_errors:
        errors.append(
            f"{MANIFEST_PATH}:{_json_path(list(error.absolute_path))}: {error.message}"
        )
    if manifest_errors:
        return errors

    inventory_errors = validate_contract_manifest(root, manifest)
    errors.extend(inventory_errors)
    if inventory_errors:
        return errors

    registry = registry_from_manifest(manifest)
    versions = {
        entry["id"]: entry["documentSchemaVersion"]
        for entry in manifest["contracts"]
    }
    documents: dict[str, Any] = {}
    all_documents_structurally_valid = True

    for name, (contract_path, schema_path) in registry.items():
        try:
            document = load_json(root / contract_path)
        except _load_json_error_types() as exc:
            errors.append(f"{contract_path}: unable to load JSON: {exc}")
            all_documents_structurally_valid = False
            continue

        schema = _validate_schema(root, schema_path, errors)
        if schema is None:
            all_documents_structurally_valid = False
            continue

        expected_schema_uri = f"../{schema_path}"
        if isinstance(document, dict) and document.get("$schema") != expected_schema_uri:
            errors.append(
                f"{contract_path}: declared schema does not match manifest: "
                f"expected {expected_schema_uri!r}, got {document.get('$schema')!r}"
            )
            all_documents_structurally_valid = False

        if isinstance(document, dict) and document.get("schemaVersion") != versions[name]:
            errors.append(
                f"{contract_path}: schemaVersion does not match manifest: "
                f"expected {versions[name]!r}, got {document.get('schemaVersion')!r}"
            )
            all_documents_structurally_valid = False

        documents[name] = document
        validator = Draft202012Validator(schema)
        try:
            document_errors = sorted(
                validator.iter_errors(document),
                key=lambda item: _json_path(list(item.absolute_path)),
            )
        except Unresolvable as exc:
            errors.append(
                f"{schema_path}: unresolved JSON Schema reference: {exc}"
            )
            all_documents_structurally_valid = False
            continue
        if document_errors:
            all_documents_structurally_valid = False
        for error in document_errors:
            errors.append(
                f"{contract_path}:{_json_path(list(error.absolute_path))}: {error.message}"
            )

    if all_documents_structurally_valid and len(documents) == len(registry):
        errors.extend(cross_validate(copy.deepcopy(documents)))

    return errors


def main() -> int:
    errors = validate_repository(ROOT)
    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All web-application contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
