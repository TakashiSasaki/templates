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
    plan_target,
    resolve_configuration,
    sha256_bytes,
)


class CompositionPlaygroundProjectionTests(unittest.TestCase):
    def test_lookup_key_rejects_duplicate_unexposed_and_unsafe_input(self) -> None:
        optionals = ["capability.cli", "lifecycle.composition-state"]
        with self.assertRaisesRegex(CompositionError, "duplicate") as duplicate:
            playground.case_key(
                "skill", ["capability.cli", "capability.cli"], optionals
            )
        self.assertEqual("DUPLICATE_COMPONENT", duplicate.exception.code)

        with self.assertRaises(CompositionError) as unexposed:
            playground.case_key("skill", ["capability.pwa"], optionals)
        self.assertEqual("COMPONENT_NOT_EXPOSED", unexposed.exception.code)

        with self.assertRaises(CompositionError) as unsafe:
            playground.case_key("../skill", [], optionals)
        self.assertEqual("INVALID_RECIPE", unsafe.exception.code)

        with self.assertRaises(CompositionError) as bad_mask:
            playground.explicit_includes_for_mask(optionals, 4)
        self.assertEqual("INVALID_INCLUDE_MASK", bad_mask.exception.code)

    def test_projection_matches_canonical_composer_for_every_v1_case(self) -> None:
        state = load_source_state()
        projection = playground.build_projection()
        recipe_by_id = {entry["id"]: entry for entry in projection["recipes"]}
        component_by_id = {
            entry["id"]: entry for entry in projection["components"]
        }
        material_by_id = {
            entry["index"]: entry for entry in projection["materials"]
        }
        outcome_by_id = {
            entry["index"]: entry for entry in projection["outcomes"]
        }

        expected_case_count = sum(
            1 << len(recipe["optional_components"])
            for recipe in state.recipes.values()
        )
        self.assertEqual(2336, expected_case_count)
        self.assertEqual(
            expected_case_count,
            sum(len(recipe["cases"]) for recipe in projection["recipes"]),
        )
        self.assertEqual(
            expected_case_count,
            sum(recipe["case_count"] for recipe in projection["recipes"]),
        )
        self.assertEqual(state.revision, projection["source"]["revision"])
        self.assertEqual(
            playground.PROVENANCE_REASON_BITS,
            projection["provenance_reason_bits"],
        )
        self.assertLess(len(playground.render_projection(projection)), 1_000_000)

        validated_outcomes: set[int] = set()
        case_keys: set[str] = set()
        for recipe_id in sorted(recipe_by_id):
            recipe_projection = recipe_by_id[recipe_id]
            self.assertEqual(
                recipe_projection["case_count"], len(recipe_projection["cases"])
            )
            for mask, case in enumerate(recipe_projection["cases"]):
                includes = playground.explicit_includes_for_mask(
                    recipe_projection["optional_components"], mask
                )
                key, normalized_mask, normalized_includes = playground.case_key(
                    recipe_id,
                    includes,
                    recipe_projection["optional_components"],
                )
                self.assertEqual(mask, normalized_mask)
                self.assertEqual(includes, normalized_includes)
                self.assertNotIn(key, case_keys)
                case_keys.add(key)

                configuration = playground.canonical_configuration(
                    recipe_id, includes
                )
                try:
                    canonical_recipe, resolved = resolve_configuration(
                        state, configuration
                    )
                except CompositionError as exc:
                    self.assertFalse(case["valid"])
                    self.assertIsNone(case["outcome_id"])
                    self.assertEqual([], case["selection_reason_masks"])
                    self.assertEqual(exc.code, case["error"]["code"])
                    continue

                self.assertTrue(case["valid"])
                self.assertIsNone(case["error"])
                outcome = outcome_by_id[case["outcome_id"]]
                self.assertEqual(resolved, outcome["resolved_components"])
                expected_edges = playground._dependency_edges(state, resolved)
                self.assertEqual(expected_edges, outcome["dependency_edges"])
                self.assertEqual(
                    playground._selection_reason_masks(
                        canonical_recipe,
                        includes,
                        resolved,
                        expected_edges,
                    ),
                    case["selection_reason_masks"],
                )
                expected_contract_ids = sorted(
                    contract_id
                    for component_id in resolved
                    for contract_id in component_by_id[component_id]["contract_ids"]
                )
                self.assertEqual(expected_contract_ids, outcome["contract_ids"])

                outcome_id = outcome["index"]
                if outcome_id in validated_outcomes:
                    continue
                validated_outcomes.add(outcome_id)
                materials = build_materials(state, resolved)
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
                        field: material_by_id[material_id][field]
                        for field in (
                            "component",
                            "destination",
                            "ownership",
                            "sha256",
                        )
                    }
                    for material_id in outcome["material_ids"]
                ]
                sort_key = lambda item: (
                    item["destination"],
                    item["component"],
                    item["sha256"],
                )
                self.assertEqual(
                    sorted(expected_materials, key=sort_key),
                    sorted(projected_materials, key=sort_key),
                    key,
                )
                with tempfile.TemporaryDirectory(
                    prefix="composition-playground-test-empty-"
                ) as directory:
                    actions, conflicts = plan_target(Path(directory), materials)
                self.assertEqual([], conflicts, key)
                self.assertEqual(
                    dict(
                        sorted(
                            Counter(
                                action["action"] for action in actions
                            ).items()
                        )
                    ),
                    outcome["initial_plan"]["action_counts"],
                    key,
                )
                self.assertEqual(
                    0, outcome["initial_plan"]["conflict_count"], key
                )

        self.assertEqual(expected_case_count, len(case_keys))
        self.assertEqual(len(projection["outcomes"]), len(validated_outcomes))


if __name__ == "__main__":
    unittest.main()
