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
        self.assertIn("Before product coding", self.text)
        self.assertIn("implementation-evidence planning state", self.text)
        self.assertIn("empty recordIds", self.text)
        self.assertIn("requiredPositiveProofKinds", self.text)
        self.assertIn("before the initial implemented-product milestone can be claimed", self.text)
        self.assertIn("Do not collapse unrelated requirements into one catch-all requirement", self.text)

    def test_prompt_is_phase_a_only_and_contains_no_precreated_change_requirement(self) -> None:
        for phrase in (
            "This file is Phase A only",
            "Every explicit REQ-* below belongs to the initial product milestone",
            "intentionally contains no Phase B requirement",
            "no prewritten list of candidate change requirements",
            "do not disclose or create the added requirement until the initial product checkpoint",
            "creates a new caller-visible requirement with a new REQ-* ID",
            "separate evaluator/user message identified as the Evaluator Change Event",
            "must not have existed earlier in this prompt",
            "Final filesystem state must not be used to reconstruct these facts",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_requires_capability_item_authority_before_coding(self) -> None:
        for phrase in (
            "move every selected capability contract that supports planning from template mode to planning mode",
            "Every capability target itemId must exactly match an item declared in the corresponding planning capability contract",
            "Web endpoints with their browser-page/backend-api/health kind",
            "MCP transports and operations with transport bindings",
            "MCP Apps Views/associations",
            "Do not start product coding until the selected capability planning contracts",
            "A phantom or misspelled target ID must be corrected in planning",
            "Preserve stable planned item IDs when enriching a planning contract into product mode",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_prompt_separates_cli_api_and_browser_evidence_strength(self) -> None:
        for phrase in (
            "Keep CLI, HTTP/API, and browser requirements distinct",
            "Static source inspection alone is insufficient proof",
            "API or CLI filter tests do not count as browser-filter proof",
            "does not count as browser-interaction proof",
            "Focus evidence must come from browser interaction",
            "This is browser-level evidence",
            "Browser requirements must bind to browser-classified planned targets",
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
            "requirementResults: one object per disclosed REQ-* ID",
            "nextWork: deterministic ordered remaining actions",
            "implementationMilestone: READY or NOT_READY",
            "releaseReadiness: READY or NOT_READY",
            "without manually interpreting the command transcript",
            "Evaluator Change Event ID",
            "first post-change product mutation",
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
