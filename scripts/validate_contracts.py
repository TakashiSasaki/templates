#!/usr/bin/env python3
"""Validate web-application contracts and their cross-file invariants."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

CONTRACT_SCHEMAS = {
    "surfaces": ("contracts/surfaces.json", "schemas/surfaces.schema.json"),
    "routes": ("contracts/routes.json", "schemas/routes.schema.json"),
    "ui_states": ("contracts/ui-states.json", "schemas/ui-states.schema.json"),
    "viewports": ("contracts/viewports.json", "schemas/viewports.schema.json"),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def _surface_dependency_cycles(surfaces: list[dict[str, Any]]) -> list[list[str]]:
    graph = {surface["id"]: surface["startupDependencies"] for surface in surfaces}
    visiting: list[str] = []
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycles.append(visiting[start:] + [node])
            return
        if node in visited or node not in graph:
            return
        visiting.append(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.pop()
        visited.add(node)

    for surface_id in graph:
        visit(surface_id)
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
        authorization = surface["authorization"]
        if authorization["mode"] == "role" and not authorization["roles"]:
            errors.append(f"surface {surface_id}: role authorization requires at least one role")
        if authorization["mode"] == "public" and authorization["roles"]:
            errors.append(f"surface {surface_id}: public authorization must not declare roles")
        for dependency in surface["startupDependencies"]:
            if dependency not in known_surfaces:
                errors.append(f"surface {surface_id}: unknown startup dependency {dependency}")
            if dependency == surface_id:
                errors.append(f"surface {surface_id}: must not depend on itself")

    for cycle in _surface_dependency_cycles(surfaces):
        errors.append(f"surface startup dependency cycle: {' -> '.join(cycle)}")

    route_paths: list[str] = []
    aliases: list[str] = []
    surfaces_by_id = {surface["id"]: surface for surface in surfaces}
    for route in routes:
        route_id = route["id"]
        route_paths.append(route["path"])
        aliases.extend(route["aliases"])
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

    ordered_viewports = sorted(viewports, key=lambda item: item["minWidthPx"])
    if ordered_viewports and ordered_viewports[0]["minWidthPx"] != 0:
        errors.append("viewport coverage must start at 0px")
    for index, viewport in enumerate(ordered_viewports):
        minimum = viewport["minWidthPx"]
        maximum = viewport.get("maxWidthPx")
        if maximum is not None and maximum < minimum:
            errors.append(f"viewport {viewport['id']}: maxWidthPx is less than minWidthPx")
        is_last = index == len(ordered_viewports) - 1
        if not is_last and maximum is None:
            errors.append(f"viewport {viewport['id']}: only the final viewport may omit maxWidthPx")
        if is_last and maximum is not None:
            errors.append(f"viewport {viewport['id']}: final viewport must be open-ended")
        if not is_last and maximum is not None:
            next_minimum = ordered_viewports[index + 1]["minWidthPx"]
            expected = maximum + 1
            if next_minimum != expected:
                relation = "overlap" if next_minimum < expected else "gap"
                errors.append(
                    f"viewport boundary {viewport['id']} -> {ordered_viewports[index + 1]['id']}: "
                    f"{relation}; expected minWidthPx {expected}, found {next_minimum}"
                )

    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    documents: dict[str, Any] = {}
    all_documents_structurally_valid = True

    for name, (contract_path, schema_path) in CONTRACT_SCHEMAS.items():
        try:
            document = load_json(root / contract_path)
            schema = load_json(root / schema_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{name}: unable to load JSON: {exc}")
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
