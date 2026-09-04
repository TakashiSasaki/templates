#!/usr/bin/env python3
"""Regression coverage for the Composition-owned Playground projection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_composition_playground as playground  # noqa: E402
from composer_core_impl import (  # noqa: E402
    CompositionError,
    build_materials,
    load_source_state,
    normalize_intent,
    plan_target,
    resolve_configuration,
    sha256_bytes,
)


class CompositionPlaygroundProjectionTests(unittest.TestCase):
    def test_lookup_key_rejects_duplicate_unexposed_and_unsafe_input(self) -> None:
        optionals = ["capability.cli", "lifecycle.composition-state"]
        with self.assertRaisesRegex(CompositionError, "duplicate") as duplicate:
            playground.case_key("skill", ["capability.cli", "capability.cli"], optionals)
        self.assertEqual("DUPLICATE_COMPONENT", duplicate.exception.code)

        with self.assertRaises(CompositionError) as unexposed:
            playground.case_key("skill", ["capability.pwa"], optionals)
        self.assertEqual("COMPONENT_NOT_EXPOSED", unexposed.exception.code)

        with self.assertRaises(CompositionError) as unsafe:
            playground.case_key("../skill", [], optionals)
        self.assertEqual("INVALID_RECIPE", unsafe.exception.code)

    def test_projection_matches_canonical_composer_for_every_v1_case(self) -> None:
        state = load_source_state()
        projection = playground.build_projection()
        recipe_by_id = {entry["id"]: entry for entry in projection["recipes"]}
        component_by_id = {entry["id"]: entry for entry in projection["components"]}
        material_by_id = {entry["index"]: entry for entry in projection["materials"]}

        expected_case_count = sum(1 << len(recipe["optional_components"]) for recipe in state.recipes.values())
        self.assertEqual(2336, expected_case_count)
        self.assertEqual(expected_case_count, len(projection["cases"]))
        self.assertEqual(expected_case_count, sum(recipe["case_count"] for recipe in projection["recipes"]))
        self.assertEqual(len(projection["cases"]), len({case["key"] for case in projection["cases"]}))
        self.assertEqual(state.revision, projection["source"]["revision"])

        representative_by_recipe: dict[str, dict[str, object]] = {}
        for case in projection["cases"]:
            recipe_projection = recipe_by_id[case["recipe"]]
            key, mask, includes = playground.case_key(
                case["recipe"],
                case["explicit_includes"],
                recipe_projection["optional_components"],
            )
            self.assertEqual(key, case["key"])
            self.assertEqual(mask, case["include_mask"])
            self.assertEqual(includes, case["explicit_includes"])
            self.assertEqual(
                {"schema_version": 1, **normalize_intent(case["configuration"])},
                case["configuration"],
            )

            try:
                canonical_recipe, resolved = resolve_configuration(state, case["configuration"])
            except CompositionError as exc:
                self.assertFalse(case["valid"])
                self.assertIsNotNone(case["error"])
                self.assertEqual(exc.code, case["error"]["code"])
                continue

            self.assertEqual(resolved, case["resolved_components"])
            provenance = {entry["component"]: entry["reasons"] for entry in case["selection_provenance"]}
            self.assertEqual(set(resolved), set(provenance))
            expected_provenance = playground._selection_provenance(
                state,
                canonical_recipe,
                case["explicit_includes"],
                resolved,
            )
            self.assertEqual(expected_provenance, case["selection_provenance"])

            expected_contract_ids = sorted(
                contract_id
                for component_id in resolved
                for contract_id in component_by_id[component_id]["contract_ids"]
            )
            self.assertEqual(expected_contract_ids, case["contract_ids"])
            if case["valid"] and case["include_mask"] == 0:
                representative_by_recipe[case["recipe"]] = case

        self.assertEqual(set(state.recipes), set(representative_by_recipe))
        for recipe_id, case in representative_by_recipe.items():
            materials = build_materials(state, case["resolved_components"])
            expected_materials = [
                {
                    "component": material.component,
                    "destination": material.destination,
                    "ownership": material.ownership,
                    "sha256": sha256_bytes(material.data),
                }
                for material in materials
            ]
            projected_materials = [
                {
                    key: material_by_id[material_id][key]
                    for key in ("component", "destination", "ownership", "sha256")
                }
                for material_id in case["material_ids"]
            ]
            self.assertEqual(
                sorted(expected_materials, key=lambda item: (item["destination"], item["component"], item["sha256"])),
                sorted(projected_materials, key=lambda item: (item["destination"], item["component"], item["sha256"])),
                recipe_id,
            )
            with tempfile.TemporaryDirectory(prefix="composition-playground-test-empty-") as directory:
                actions, conflicts = plan_target(Path(directory), materials)
            self.assertEqual([], conflicts, recipe_id)
            self.assertEqual(
                dict(sorted(Counter(action["action"] for action in actions).items())),
                case["initial_plan"]["action_counts"],
                recipe_id,
            )
            self.assertEqual(0, case["initial_plan"]["conflict_count"], recipe_id)


if __name__ == "__main__":
    unittest.main()
