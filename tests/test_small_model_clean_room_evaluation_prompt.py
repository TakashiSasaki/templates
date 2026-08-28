from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "examples/evaluations/small-model-clean-room-field-log.txt"
EXPECTED_REQUIREMENTS = {
    "REQ-FIELD-CREATE",
    "REQ-FIELD-LIST",
    "REQ-FIELD-EDIT",
    "REQ-FIELD-CLI-SEVERITY-FILTER",
    "REQ-FIELD-HTTP-SEVERITY-FILTER",
    "REQ-FIELD-BROWSER-SEVERITY-FILTER",
    "REQ-FIELD-BROWSER-EDIT",
    "REQ-FIELD-KEYBOARD-FOCUS",
    "REQ-FIELD-VIEWPORT",
    "REQ-FIELD-PERSISTENCE",
}


class SmallModelCleanRoomEvaluationPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PROMPT.read_text(encoding="utf-8")

    def test_prompt_has_stable_explicit_requirement_inventory(self) -> None:
        declared = set(re.findall(r"^REQ-[A-Z0-9-]+$", self.text, flags=re.MULTILINE))
        self.assertEqual(declared, EXPECTED_REQUIREMENTS)
        self.assertIn("https://github.com/TakashiSasaki/templates", self.text)
        self.assertIn("Determine how to use it from the repository itself", self.text)
        self.assertIn("Create the application outside the templates repository", self.text)

    def test_prompt_contains_no_repository_specific_solution_path(self) -> None:
        forbidden = (
            "composition branch",
            "Composition authority",
            "Composition lifecycle",
            "implementation-evidence",
            "requiredPositiveProofKinds",
            "recordIds",
            "itemId",
            "template mode",
            "planning mode",
            "planning checkpoint",
            "product checkpoint",
            "browser-page",
            "MCP transports",
            "MCP Apps",
            ".template-composition",
            "deterministic implementation-evidence worklist",
        )
        lowered = self.text.lower()
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), lowered)

    def test_prompt_does_not_telegraph_a_future_requirement_change(self) -> None:
        forbidden = (
            "Phase A",
            "Phase B",
            "staged change",
            "staged requirement",
            "future requirement",
            "Evaluator Change Event",
            "post-change",
            "later requirement",
            "another requirement will arrive",
        )
        lowered = self.text.lower()
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), lowered)

    def test_prompt_keeps_product_level_evidence_strength_requirements(self) -> None:
        for phrase in (
            "executable process-level test",
            "through the service boundary",
            "A real browser changes the filter",
            "API or CLI filter tests do not count as browser-filter proof",
            "does not count as browser-interaction proof",
            "Focus evidence must come from browser interaction",
            "browser proof cannot be executed",
            "do not substitute static inspection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_requires_truthful_completion_and_release_reporting(self) -> None:
        for phrase in (
            "Do not fabricate execution results",
            "implementationMilestone: READY or NOT_READY",
            "releaseReadiness: READY or NOT_READY",
            "nextWork: deterministic ordered remaining actions",
            "If required proof is unavailable, failed, or too weak, do not claim READY",
            "Use the repository's own documented validation and release checks",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_requires_machine_auditable_outputs_without_evaluator_chronology(self) -> None:
        for phrase in (
            "evaluation-result.json",
            "requirementResults: one object per REQ-* requirement listed in this task",
            "validation results and exit statuses",
            "evaluation-report.md",
            "command-log.md",
            "the consumer application and its tests",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)
        self.assertNotIn("disclosure order", self.text)
        self.assertNotIn("first post-change product mutation", self.text)


if __name__ == "__main__":
    unittest.main()
