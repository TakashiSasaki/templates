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
        self.assertIn("before claiming implementation completion", self.text)
        self.assertIn("Do not collapse unrelated requirements into one catch-all requirement", self.text)

    def test_prompt_separates_cli_api_and_browser_evidence_strength(self) -> None:
        for phrase in (
            "Keep CLI, HTTP/API, and browser requirements distinct",
            "Static source inspection alone is insufficient proof",
            "API or CLI filter tests do not count as browser-filter proof",
            "does not count as browser-interaction proof",
            "Focus evidence must come from browser interaction",
            "This is browser-level evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_requires_truthful_deferred_and_release_blocking(self) -> None:
        for phrase in (
            "record the unavailable proof as deferred",
            "Release readiness must remain NOT READY",
            "no required evidence is missing or deferred",
            "If any one of these conditions is false, say NOT READY",
            "Do not fabricate execution results",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_requires_machine_auditable_results_and_next_work(self) -> None:
        for phrase in (
            "evaluation-result.json",
            "requirementResults: one object per explicit REQ-* ID",
            "nextWork: deterministic ordered remaining actions",
            "implementationMilestone: READY or NOT_READY",
            "releaseReadiness: READY or NOT_READY",
            "without manually interpreting the command transcript",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_does_not_treat_one_successful_run_as_proof_of_general_robustness(self) -> None:
        self.assertIn(
            "A single successful run is evidence that the workflow can work; it does not prove that small models will always use it correctly.",
            self.text,
        )
        self.assertIn("Record the model and exact templates revision", self.text)


if __name__ == "__main__":
    unittest.main()
