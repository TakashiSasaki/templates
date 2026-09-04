#!/usr/bin/env python3
"""Generate the canonical Composition Playground v1 projection."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from jsonschema import Draft202012Validator

from composer_core_impl import (
    CANONICAL_REPOSITORY,
    CompositionError,
    build_materials,
    load_json_bytes,
    load_source_state,
    normalize_intent,
    plan_target,
    read_json,
    resolve_configuration,
    sha256_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_SCHEMA = ROOT / "schemas/composition-playground-projection.schema.json"
PROJECTION_ID = "composition-playground-v1"
SEMANTIC_PATHS = (
    "catalog",
    "recipes",
    "components",
    "schemas/catalog.schema.json",
    "schemas/component.schema.json",
    "schemas/recipe.schema.json",
    "schemas/composition-config.schema.json",
    "schemas/composition-playground-projection.schema.json",
    "scripts/composer_core.py",
    "scripts/composer_core_impl.py",
    "scripts/generate_composition_playground.py",
)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise CompositionError("GIT_UNAVAILABLE", f"cannot execute git: {exc}") from exc
    if check and result.returncode != 0:
        raise CompositionError(
            "GIT_FAILED",
            f"git {' '.join(args)} failed: {result.stderr.strip()}",
        )
    return result


def projection_source_revision(head_revision: str, requested_revision: str | None) -> str:
    """Bind projection provenance to an exact semantically equivalent ancestor."""
    if requested_revision is None:
        return head_revision
    if not re.fullmatch(r"[0-9a-f]{40}", requested_revision) or requested_revision == "0" * 40:
        raise CompositionError(
            "INVALID_SOURCE_REVISION",
            f"invalid Playground source revision: {requested_revision!r}",
        )
    if requested_revision == head_revision:
        return requested_revision
    ancestor = _git("merge-base", "--is-ancestor", requested_revision, head_revision, check=False)
    if ancestor.returncode == 1:
        raise CompositionError(
            "PLAYGROUND_SOURCE_NOT_ANCESTOR",
            f"projection source {requested_revision} is not an ancestor of {head_revision}",
        )
    if ancestor.returncode != 0:
        raise CompositionError(
            "GIT_FAILED",
            f"cannot verify Playground source ancestry: {ancestor.stderr.strip()}",
        )
    diff = _git(
        "diff",
        "--quiet",
        requested_revision,
        head_revision,
        "--",
        *SEMANTIC_PATHS,
        check=False,
    )
    if diff.returncode == 1:
        raise CompositionError(
            "STALE_PLAYGROUND_SOURCE",
            "Composition semantics changed after the projection source revision",
        )
    if diff.returncode != 0:
        raise CompositionError(
            "GIT_FAILED",
            f"cannot compare Playground semantic inputs: {diff.stderr.strip()}",
        )
    return requested_revision


def case_key(
    recipe_id: str,
    includes: Sequence[str],
    optional_components: Sequence[str],
) -> tuple[str, int, list[str]]:
    """Return the stable lookup key without performing Composition resolution."""
    if not isinstance(recipe_id, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", recipe_id):
        raise CompositionError("INVALID_RECIPE", f"unsafe recipe id for Playground lookup: {recipe_id!r}")
    if any(not isinstance(item, str) for item in includes):
        raise CompositionError("INVALID_COMPONENT", "Playground includes must be component id strings")
    if len(includes) != len(set(includes)):
        raise CompositionError("DUPLICATE_COMPONENT", "Playground includes contain duplicate components")
    ordered = sorted(optional_components)
    if len(ordered) != len(set(ordered)):
        raise CompositionError("INVALID_RECIPE", f"recipe {recipe_id} exposes duplicate optional components")
    index = {component_id: position for position, component_id in enumerate(ordered)}
    unknown = sorted(set(includes) - set(ordered))
    if unknown:
        raise CompositionError(
            "COMPONENT_NOT_EXPOSED",
            f"recipe {recipe_id} does not expose optional components: {unknown}",
        )
    normalized = sorted(includes)
    mask = sum(1 << index[component_id] for component_id in normalized)
    return f"{recipe_id}:{mask:x}", mask, normalized


def _contract_inventory(state: Any) -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    seen_documents: set[str] = set()
    seen_schemas: set[str] = set()
    for component_id in sorted(state.components):
        registrations = sorted(
            state.components[component_id].get("contract_registrations", []),
            key=lambda item: (item["id"], item["document"], item["schema"]),
        )
        for registration in registrations:
            if registration["id"] in seen_ids:
                raise CompositionError(
                    "DUPLICATE_CONTRACT_REGISTRATION",
                    f"duplicate contract id in Playground inventory: {registration['id']}",
                )
            if registration["document"] in seen_documents:
                raise CompositionError(
                    "DUPLICATE_CONTRACT_REGISTRATION",
                    f"duplicate contract document in Playground inventory: {registration['document']}",
                )
            if registration["schema"] in seen_schemas:
                raise CompositionError(
                    "DUPLICATE_CONTRACT_REGISTRATION",
                    f"duplicate contract schema in Playground inventory: {registration['schema']}",
                )
            seen_ids.add(registration["id"])
            seen_documents.add(registration["document"])
            seen_schemas.add(registration["schema"])
            rows.append((component_id, registration))
    rows.sort(key=lambda item: (item[1]["id"], item[0]))
    contracts: list[dict[str, Any]] = []
    by_component: dict[str, list[int]] = {component_id: [] for component_id in state.components}
    for index, (component_id, registration) in enumerate(rows):
        contracts.append(
            {
                "index": index,
                "component": component_id,
                "id": registration["id"],
                "document": registration["document"],
                "schema": registration["schema"],
                "document_schema_version": registration["document_schema_version"],
                "purpose": registration["purpose"],
            }
        )
        by_component[component_id].append(index)
    return contracts, by_component


def _selection_provenance(
    state: Any,
    recipe: dict[str, Any],
    explicit_includes: Sequence[str],
    resolved: Sequence[str],
) -> list[dict[str, Any]]:
    selected = set(resolved)
    explicit = set(explicit_includes)
    rows: list[dict[str, Any]] = []
    for component_id in sorted(resolved):
        reasons: list[dict[str, str]] = []
        if component_id == recipe["artifact"]:
            reasons.append({"kind": "recipe-artifact"})
        if component_id in recipe["required_components"]:
            reasons.append({"kind": "recipe-required"})
        if component_id in recipe["default_components"]:
            reasons.append({"kind": "recipe-default"})
        if component_id in explicit:
            reasons.append({"kind": "explicit-include"})
        for parent in sorted(selected):
            if component_id in state.components[parent]["requires"]:
                reasons.append({"kind": "dependency", "from_component": parent})
        if not reasons:
            raise CompositionError(
                "UNEXPLAINED_PLAYGROUND_SELECTION",
                f"canonical resolved component has no projection provenance: {component_id}",
            )
        rows.append({"component": component_id, "reasons": reasons})
    return rows


def _configuration(recipe_id: str, includes: Sequence[str]) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "recipe": recipe_id,
        "components": {"include": list(includes), "exclude": []},
        "parameters": {},
    }
    normalized = normalize_intent(value)
    return {"schema_version": 1, **normalized}


def _validate_projection(projection: dict[str, Any]) -> None:
    schema = read_json(PROJECTION_SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(projection),
        key=lambda error: tuple(error.absolute_path),
    )
    if errors:
        rendered = "; ".join(error.message for error in errors[:8])
        raise CompositionError("INVALID_PLAYGROUND_PROJECTION", rendered)


def build_projection(*, source_revision: str | None = None) -> dict[str, Any]:
    state = load_source_state()
    bound_revision = projection_source_revision(state.revision, source_revision)
    contracts, contract_ids_by_component = _contract_inventory(state)

    recipes: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    for component_id in sorted(state.components):
        descriptor = state.components[component_id]
        components.append(
            {
                "id": component_id,
                "role": descriptor["component_role"],
                "version": descriptor["version"],
                "summary": descriptor["summary"],
                "requires": sorted(descriptor["requires"]),
                "conflicts": sorted(descriptor["conflicts"]),
                "contract_ids": contract_ids_by_component[component_id],
                "material_declarations": descriptor["materials"],
                "source_path": f"components/{component_id}/component.json",
            }
        )

    material_cache: dict[tuple[str, ...], tuple[list[tuple[str, str, str, str]], dict[str, Any]]] = {}
    all_material_keys: set[tuple[str, str, str, str]] = set()
    cases: list[dict[str, Any]] = []

    for recipe_id in sorted(state.recipes):
        recipe = state.recipes[recipe_id]
        optionals = sorted(recipe["optional_components"])
        recipes.append(
            {
                "id": recipe_id,
                "artifact": recipe["artifact"],
                "required_components": sorted(recipe["required_components"]),
                "default_components": sorted(recipe["default_components"]),
                "optional_components": optionals,
                "case_count": 1 << len(optionals),
                "source_path": f"recipes/{recipe_id}.json",
            }
        )
        for mask in range(1 << len(optionals)):
            raw_includes = [component_id for position, component_id in enumerate(optionals) if mask & (1 << position)]
            key, normalized_mask, includes = case_key(recipe_id, raw_includes, optionals)
            config = _configuration(recipe_id, includes)
            resolved: list[str] = []
            provenance: list[dict[str, Any]] = []
            case_contract_ids: list[int] = []
            material_keys: list[tuple[str, str, str, str]] = []
            initial_plan: dict[str, Any] | None = None
            error: dict[str, str] | None = None
            try:
                canonical_recipe, resolved = resolve_configuration(state, config)
                provenance = _selection_provenance(state, canonical_recipe, includes, resolved)
                case_contract_ids = sorted(
                    contract_id
                    for component_id in resolved
                    for contract_id in contract_ids_by_component[component_id]
                )
                closure_key = tuple(resolved)
                cached = material_cache.get(closure_key)
                if cached is None:
                    materials = build_materials(state, resolved)
                    with tempfile.TemporaryDirectory(prefix="composition-playground-empty-") as directory:
                        actions, conflicts = plan_target(Path(directory), materials)
                    if conflicts:
                        raise CompositionError(
                            "PLAYGROUND_EMPTY_TARGET_CONFLICT",
                            "; ".join(conflicts),
                        )
                    action_counts = dict(sorted(Counter(action["action"] for action in actions).items()))
                    material_keys_for_closure = [
                        (
                            material.component,
                            material.destination,
                            material.ownership,
                            sha256_bytes(material.data),
                        )
                        for material in materials
                    ]
                    cached = (
                        material_keys_for_closure,
                        {"action_counts": action_counts, "conflict_count": 0},
                    )
                    material_cache[closure_key] = cached
                material_keys, initial_plan = cached
                all_material_keys.update(material_keys)
            except CompositionError as exc:
                error = {"code": exc.code, "message": exc.message}
            cases.append(
                {
                    "key": key,
                    "recipe": recipe_id,
                    "include_mask": normalized_mask,
                    "explicit_includes": includes,
                    "configuration": config,
                    "valid": error is None,
                    "error": error,
                    "resolved_components": resolved,
                    "selection_provenance": provenance,
                    "contract_ids": case_contract_ids,
                    "_material_keys": material_keys,
                    "initial_plan": initial_plan,
                }
            )

    ordered_material_keys = sorted(all_material_keys, key=lambda item: (item[1], item[0], item[2], item[3]))
    material_index = {key: index for index, key in enumerate(ordered_material_keys)}
    materials = [
        {
            "index": index,
            "component": key[0],
            "destination": key[1],
            "ownership": key[2],
            "sha256": key[3],
        }
        for index, key in enumerate(ordered_material_keys)
    ]
    for case in cases:
        case["material_ids"] = sorted(material_index[key] for key in case.pop("_material_keys"))

    projection = {
        "schema_version": 1,
        "projection_id": PROJECTION_ID,
        "source": {
            "repository": CANONICAL_REPOSITORY,
            "authority": "composition",
            "revision": bound_revision,
        },
        "scope": {
            "mode": "initial",
            "target": "empty",
            "components_exclude": [],
            "parameters": {},
        },
        "recipes": recipes,
        "components": components,
        "contracts": contracts,
        "materials": materials,
        "cases": cases,
    }
    _validate_projection(projection)
    return projection


def render_projection(projection: dict[str, Any]) -> bytes:
    return (json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _revision_from_existing(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CompositionError("READ_FAILED", f"cannot read projection {path}: {exc}") from exc
    value = load_json_bytes(data, label=str(path))
    try:
        revision = value["source"]["revision"]
    except (KeyError, TypeError) as exc:
        raise CompositionError("INVALID_PLAYGROUND_PROJECTION", "projection has no source revision") from exc
    if not isinstance(revision, str):
        raise CompositionError("INVALID_PLAYGROUND_PROJECTION", "projection source revision is not a string")
    return revision


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path, help="write generated projection to this path")
    output.add_argument("--check", type=Path, help="fail unless this file is the deterministic current projection")
    parser.add_argument(
        "--source-revision",
        help="bind to a semantically equivalent exact ancestor revision; defaults to HEAD",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        requested_revision = args.source_revision
        if args.check is not None and requested_revision is None:
            requested_revision = _revision_from_existing(args.check)
        rendered = render_projection(build_projection(source_revision=requested_revision))
        if args.check is not None:
            try:
                existing = args.check.read_bytes()
            except OSError as exc:
                raise CompositionError("READ_FAILED", f"cannot read projection {args.check}: {exc}") from exc
            if existing != rendered:
                raise CompositionError(
                    "STALE_PLAYGROUND_PROJECTION",
                    f"{args.check} is not the deterministic canonical Playground projection",
                )
            print(f"Composition Playground projection is current: {args.check}")
            return 0
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(args.output)
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except CompositionError as exc:
        print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
