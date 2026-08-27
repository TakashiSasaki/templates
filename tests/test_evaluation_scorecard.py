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
        self.assertEqual(self.schema["properties"]["next_clean_room_rerun_conditions"]["minItems"], 1)

    def test_guide_covers_requested_dimensions_and_environment(self) -> None:
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
        ):
            self.assertIn(phrase, self.text)

    def test_valid_scorecard_instance_and_invalid_status(self) -> None:
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
        payload = {
            "schema_version": 1,
            "evaluation_id": "test",
            "environment_fingerprint": environment,
            "dimensions": dimensions,
            "next_clean_room_rerun_conditions": ["fresh independent conversation"],
        }
        validator = Draft202012Validator(self.schema)
        validator.validate(payload)
        invalid = json.loads(json.dumps(payload))
        invalid["dimensions"]["dead_ends"]["status"] = "UNKNOWN"
        with self.assertRaises(ValidationError):
            validator.validate(invalid)

    def test_guide_preserves_clean_room_boundary(self) -> None:
        self.assertIn("future clean-room run", self.text)
        self.assertIn("this maintenance conversation is not an eligible evaluator", self.text)
        self.assertIn("Do not convert BLOCKED or NOT TESTED into PASS", self.text)


if __name__ == "__main__":
    unittest.main()
