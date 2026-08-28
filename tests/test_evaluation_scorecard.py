from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "examples/evaluations/evaluation-scorecard.schema.json"
GUIDE = ROOT / "examples/evaluations/evaluation-scorecard.txt"


class EvaluationScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.text = GUIDE.read_text(encoding="utf-8")

    def payload(self, *, lifecycle_status: str = "PASS", applicable: bool = True) -> dict:
        score = {"status": "PASS", "attribution": "repository defect", "notes": "controlled"}
        environment = {
            "model": "test-model",
            "fresh_conversation": True,
            "outside_maintainer_workspace": True,
            "inherited_instructions_recorded": True,
            "available_tools": ["github"],
            "git_availability": "available",
            "browser_availability": "available",
            "network_restrictions": "none",
            "user_intervention_count": 0,
            "transcript_completeness": "complete",
        }
        dimensions = {
            key: dict(score)
            for key in self.schema["properties"]["dimensions"]["required"]
        }
        dimensions["lifecycle_correctness"]["status"] = lifecycle_status
        chronology = {
            "checkpoint_lifecycle_applicable": applicable,
            "planning_checkpoint_preceded_product_coding": True if applicable else None,
            "product_checkpoint_preceded_release_readiness": True if applicable else None,
            "planning_boundary_evidence": "planning checkpoint observed before first product mutation",
            "product_boundary_evidence": "product checkpoint observed before readiness evaluation",
        }
        return {
            "schema_version": 2,
            "evaluation_id": "test",
            "environment_fingerprint": environment,
            "dimensions": dimensions,
            "lifecycle_chronology": chronology,
            "next_clean_room_rerun_conditions": ["fresh independent conversation"],
        }

    def test_schema_contains_fixed_statuses_attributions_and_dimensions(self) -> None:
        score = self.schema["$defs"]["score"]
        self.assertEqual(
            score["properties"]["status"]["enum"],
            ["PASS", "FAIL", "BLOCKED", "NOT TESTED"],
        )
        self.assertEqual(
            score["properties"]["attribution"]["enum"],
            [
                "repository defect",
                "documentation/discoverability defect",
                "machine-contract defect",
                "evaluator mistake",
                "environment limitation",
                "evidence-capture limitation",
            ],
        )
        dimensions = self.schema["properties"]["dimensions"]
        self.assertEqual(len(dimensions["required"]), 13)
        self.assertEqual(set(dimensions["required"]), set(dimensions["properties"]))
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 2)
        self.assertIn("lifecycle_chronology", self.schema["required"])
        self.assertEqual(self.schema["properties"]["next_clean_room_rerun_conditions"]["minItems"], 1)

    def test_guide_covers_requested_dimensions_environment_and_chronology(self) -> None:
        for phrase in (
            "Entry-point discovery",
            "Machine bootstrap discovery",
            "Canonical bootstrap execution",
            "Integrity verification",
            "Installer / Skill / toolchain role separation",
            "Lifecycle correctness",
            "Managed/generated boundary",
            "Product evidence completion",
            "Browser proof handling",
            "Release-readiness honesty",
            "Recovery quality",
            "User intervention",
            "Dead ends",
            "fresh conversation",
            "complete transcript capture",
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
            "does not retroactively make the planning boundary pass",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_valid_scorecard_instance_and_invalid_common_shapes(self) -> None:
        payload = self.payload()
        validator = Draft202012Validator(self.schema)
        validator.validate(payload)
        invalid_cases = (
            ("invalid status", lambda value: value["dimensions"]["dead_ends"].__setitem__("status", "UNKNOWN")),
            ("invalid attribution", lambda value: value["dimensions"]["dead_ends"].__setitem__("attribution", "unknown attribution")),
            ("invalid transcript completeness", lambda value: value["environment_fingerprint"].__setitem__("transcript_completeness", "other")),
            ("negative intervention count", lambda value: value["environment_fingerprint"].__setitem__("user_intervention_count", -1)),
            ("empty rerun conditions", lambda value: value.__setitem__("next_clean_room_rerun_conditions", [])),
            ("empty model", lambda value: value["environment_fingerprint"].__setitem__("model", "")),
            ("empty rerun condition", lambda value: value.__setitem__("next_clean_room_rerun_conditions", [""])),
            ("extra root property", lambda value: value.__setitem__("unexpected", True)),
            ("extra score property", lambda value: value["dimensions"]["dead_ends"].__setitem__("unexpected", True)),
            ("missing chronology", lambda value: value.pop("lifecycle_chronology")),
            ("empty planning evidence", lambda value: value["lifecycle_chronology"].__setitem__("planning_boundary_evidence", "")),
        )
        for name, mutate in invalid_cases:
            with self.subTest(case=name):
                invalid = json.loads(json.dumps(payload))
                mutate(invalid)
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)

    def test_lifecycle_pass_requires_both_checkpoint_boundaries_in_order(self) -> None:
        validator = Draft202012Validator(self.schema)
        for field in (
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
        ):
            with self.subTest(field=field):
                payload = self.payload(lifecycle_status="PASS", applicable=True)
                payload["lifecycle_chronology"][field] = False
                with self.assertRaises(ValidationError):
                    validator.validate(payload)

        failed = self.payload(lifecycle_status="FAIL", applicable=True)
        failed["lifecycle_chronology"]["planning_checkpoint_preceded_product_coding"] = False
        validator.validate(failed)

    def test_non_applicable_checkpoint_lifecycle_requires_null_chronology_flags(self) -> None:
        validator = Draft202012Validator(self.schema)
        payload = self.payload(applicable=False)
        validator.validate(payload)
        for field in (
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
        ):
            with self.subTest(field=field):
                invalid = self.payload(applicable=False)
                invalid["lifecycle_chronology"][field] = True
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)

    def test_guide_preserves_clean_room_boundary(self) -> None:
        self.assertIn("future clean-room run", self.text)
        self.assertIn("this maintenance conversation is not an eligible evaluator", self.text)
        self.assertIn("Do not convert BLOCKED or NOT TESTED into PASS", self.text)
        self.assertIn("final repository later contains both checkpoints", self.text)


if __name__ == "__main__":
    unittest.main()
