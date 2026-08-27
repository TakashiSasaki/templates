from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "examples/evaluations/evaluation-scorecard.schema.json"
GUIDE = ROOT / "examples/evaluations/evaluation-scorecard.md"


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
        self.assertEqual(len(self.schema["properties"]["dimensions"]["required"]), 13)

    def test_guide_covers_requested_dimensions_and_environment(self) -> None:
        for phrase in (
            "Entry-point discovery",
            "Machine bootstrap discovery",
            "Canonical bootstrap execution",
            "Integrity verification",
            "Lifecycle correctness",
            "Product evidence completion",
            "Browser proof handling",
            "Release-readiness honesty",
            "Recovery quality",
            "Dead ends",
            "fresh conversation",
            "complete transcript capture",
        ):
            self.assertIn(phrase, self.text)

    def test_guide_preserves_clean_room_boundary(self) -> None:
        self.assertIn("future clean-room run", self.text)
        self.assertIn("this maintenance conversation is not an eligible evaluator", self.text)
        self.assertIn("Do not convert BLOCKED or NOT TESTED into PASS", self.text)


if __name__ == "__main__":
    unittest.main()
