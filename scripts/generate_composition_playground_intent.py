#!/usr/bin/env python3
"""Generate compact explicit-exclusion transitions beside the Playground v1 projection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from composer_core_impl import CompositionError, load_source_state, normalize_intent, read_json, resolve_configuration
from generate_composition_playground import build_projection, explicit_includes_for_mask

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/composition-playground-intent.schema.json"


def _config(recipe_id: str, includes: list[str], exclude: str) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "recipe": recipe_id,
        "components": {"include": includes, "exclude": [exclude]},
        "parameters": {},
    }
    return {"schema_version": 1, **normalize_intent(value)}


def decode_transition(projection: dict[str, Any], encoded: int) -> dict[str, Any]:
    """Decode one indexed transition without performing Composition resolution."""
    if encoded >= 0:
        return {"valid": True, "error": None, "outcome_id": encoded}
    error_index = -encoded - 1
    errors = projection.get("errors", [])
    if error_index < 0 or error_index >= len(errors):
        raise CompositionError("INVALID_PLAYGROUND_INTENT_PROJECTION", "encoded error index is out of range")
    return {"valid": False, "error": errors[error_index], "outcome_id": None}


def build_intent_projection(*, source_revision: str | None = None) -> dict[str, Any]:
    base = build_projection(source_revision=source_revision)
    state = load_source_state()
    outcomes = {tuple(row["resolved_components"]): row["index"] for row in base["outcomes"]}
    errors: list[dict[str, str]] = []
    error_indexes: dict[tuple[str, str], int] = {}
    recipes: list[dict[str, Any]] = []

    for base_recipe in base["recipes"]:
        recipe_id = base_recipe["id"]
        optionals = list(base_recipe["optional_components"])
        cases: list[list[int]] = []
        for case_index in range(base_recipe["case_count"]):
            includes = explicit_includes_for_mask(optionals, case_index)
            transitions: list[int] = []
            for component_id in optionals:
                try:
                    _, resolved = resolve_configuration(state, _config(recipe_id, includes, component_id))
                    outcome_id = outcomes.get(tuple(resolved))
                    if outcome_id is None:
                        raise CompositionError(
                            "UNPROJECTED_EXCLUSION_OUTCOME",
                            f"explicit exclusion produced an outcome absent from the resolution projection: {recipe_id} / {component_id}",
                        )
                    transitions.append(outcome_id)
                except CompositionError as exc:
                    key = (exc.code, exc.message)
                    error_index = error_indexes.get(key)
                    if error_index is None:
                        error_index = len(errors)
                        error_indexes[key] = error_index
                        errors.append({"code": exc.code, "message": exc.message})
                    transitions.append(-(error_index + 1))
            cases.append(transitions)
        recipes.append({
            "id": recipe_id,
            "optional_components": optionals,
            "case_count": base_recipe["case_count"],
            "cases": cases,
        })

    projection = {
        "schema_version": 1,
        "projection_id": "composition-playground-intent-v1",
        "source": base["source"],
        "resolution_projection_id": base["projection_id"],
        "strategy": "indexed-single-explicit-exclusion-transitions",
        "encoding": {
            "nonnegative": "canonical outcome id",
            "negative": "-(error index + 1)",
        },
        "errors": errors,
        "recipes": recipes,
    }
    schema = read_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    validation_errors = sorted(Draft202012Validator(schema).iter_errors(projection), key=lambda error: tuple(error.absolute_path))
    if validation_errors:
        raise CompositionError("INVALID_PLAYGROUND_INTENT_PROJECTION", "; ".join(error.message for error in validation_errors[:8]))
    return projection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision")
    parser.add_argument("--output")
    args = parser.parse_args()
    value = build_intent_projection(source_revision=args.source_revision)
    rendered = json.dumps(value, indent=2, sort_keys=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
