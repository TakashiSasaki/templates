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

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
VISUALLY_BLANK_CHARACTERS = {"\u2800", "\U00013441", "\U00013442", "\U0001D159"}

CONTRACT_SCHEMAS = {
    "surfaces": ("contracts/surfaces.json", "schemas/surfaces.schema.json"),
    "routes": ("contracts/routes.json", "schemas/routes.schema.json"),
    "ui_states": ("contracts/ui-states.json", "schemas/ui-states.schema.json"),
    "viewports": ("contracts/viewports.json", "schemas/viewports.schema.json"),
}


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


def load_contract_documents(root: Path) -> dict[str, Any]:
    return {
        name: load_json(root / contract_path)
        for name, (contract_path, _) in CONTRACT_SCHEMAS.items()
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
    """Return whether text contains a visible base character.

    Unicode control, format, surrogate, private-use, unassigned, combining-mark,
    and separator categories do not independently provide visible content.
    Some symbol- and letter-category characters are also intentionally blank
    and are explicitly excluded.
    """

    return any(
        character not in VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def _surface_dependency_cycles(surfaces: list[dict[str, Any]]) -> list[list[str]]:
    graph = {surface["id"]: surface["startupDependencies"] for surface in surfaces}
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
    known_states = set(state_ids)

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
            errors.append(f"surface {surface_id}: role authorization requires at least one role")
        if authorization_mode in {"public", "authenticated"} and authorization["roles"]:
            errors.append(f"surface {surface_id}: {authorization_mode} authorization must not declare roles")
        if authorization_mode == "public" and authentication == "required":
            errors.append(f"surface {surface_id}: public authorization must not require authentication")
        if authorization_mode in {"authenticated", "role"} and authentication != "required":
            errors.append(
                f"surface {surface_id}: {authorization_mode} authorization requires authentication required"
            )
        if authentication == "required" and "anonymous" in surface["audiences"]:
            errors.append(
                f"surface {surface_id}: required authentication must not include anonymous audience"
            )
        for dependency in surface["startupDependencies"]:
            if dependency not in known_surfaces:
                errors.append(f"surface {surface_id}: unknown startup dependency {dependency}")
            if dependency == surface_id:
                errors.append(f"surface {surface_id}: must not depend on itself")

    for cycle in _surface_dependency_cycles(surfaces):
        errors.append(f"surface startup dependency cycle: {' -> '.join(cycle)}")

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
    for route in routes:
        route_id = route["id"]
        route_paths.append(route["path"])
        aliases.extend(route["aliases"])
        if not _has_visible_character(route["accessibility"]["focusTarget"]):
            errors.append(f"route {route_id}: focusTarget must contain at least one visible character")
        if route["surface"] not in known_surfaces:
            errors.append(f"route {route_id}: unknown surface {route['surface']}")
        else:
            surface = surfaces_by_id[route["surface"]]
            if route["authentication"] != surface["authentication"]:
                errors.append(
                    f"route {route_id}: authentication {route['authentication']} does not match "
                    f"surface {surface['id']} ({surface['authentication']})"
                )
        for state_id in route["states"]:
            if state_id not in known_states:
                errors.append(f"route {route_id}: unknown UI state {state_id}")
        if route["path"] in route["aliases"]:
            errors.append(f"route {route_id}: canonical path is also listed as an alias")

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


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    documents: dict[str, Any] = {}
    all_documents_structurally_valid = True
    load_errors = (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateKeyError,
        NonStandardJsonConstantError,
    )

    for name, (contract_path, schema_path) in CONTRACT_SCHEMAS.items():
        try:
            document = load_json(root / contract_path)
        except load_errors as exc:
            errors.append(f"{contract_path}: unable to load JSON: {exc}")
            all_documents_structurally_valid = False
            continue

        try:
            schema = load_json(root / schema_path)
        except load_errors as exc:
            errors.append(f"{schema_path}: unable to load JSON: {exc}")
            all_documents_structurally_valid = False
            continue

        declared_dialect = schema.get("$schema") if isinstance(schema, dict) else None
        if declared_dialect != SCHEMA_DIALECT:
            errors.append(
                f"{schema_path}: unsupported JSON Schema dialect: "
                f"expected {SCHEMA_DIALECT!r}, got {declared_dialect!r}"
            )
            all_documents_structurally_valid = False
            continue

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            errors.append(f"{schema_path}: invalid JSON Schema: {exc.message}")
            all_documents_structurally_valid = False
            continue

        documents[name] = document
        validator = Draft202012Validator(schema)
        document_errors = sorted(
            validator.iter_errors(document),
            key=lambda item: _json_path(list(item.absolute_path)),
        )
        if document_errors:
            all_documents_structurally_valid = False
        for error in document_errors:
            errors.append(f"{contract_path}:{_json_path(list(error.absolute_path))}: {error.message}")

    if all_documents_structurally_valid and len(documents) == len(CONTRACT_SCHEMAS):
        errors.extend(cross_validate(copy.deepcopy(documents)))

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_repository(root)
    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("All web-application contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
