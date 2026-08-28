from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "examples/evaluations/small-model-clean-room-protocol.txt"


class SmallModelCleanRoomProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PROTOCOL.read_text(encoding="utf-8")

    def test_protocol_requires_clean_room_isolation(self) -> None:
        for phrase in (
            "fresh conversation",
            "outside the repository maintainer's project and workspace",
            "no previous reports, transcripts, artifacts",
            "commit SHAs, authority branch names, or entry-point paths",
            "inherited system, project, workspace, repository-local, or tool instructions",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)
        self.assertIn("current maintenance conversation must never be described as a clean-room run", self.text)

    def test_protocol_separates_agent_visible_task_from_evaluator_orchestration(self) -> None:
        for phrase in (
            "Agent-visible task boundary",
            "product requirements, repository URL, proof expectations, and required outputs",
            "must not prescribe repository-specific solution mechanics",
            "internal contract or schema field names",
            "component IDs, lifecycle-stage names, validator names, action names, or checkpoint commands",
            "must not announce that a later requirement will arrive",
            "The first signal of the added requirement must be the actual evaluator/user message",
            "Evaluator-side chronology and scoring rules are not part of the agent-visible task",
            "do not point the agent at evaluation fixtures as an alternate bootstrap path",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_protocol_records_environment_and_harness_boundaries(self) -> None:
        for phrase in (
            "available tools and capabilities",
            "Git availability",
            "browser availability",
            "WebDriver availability",
            "network policy",
            "user intervention count",
            "complete transcript",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_protocol_separates_lifecycle_and_attribution(self) -> None:
        for phrase in (
            "scaffold validation",
            "planning checkpoint creation",
            "first product-code mutation",
            "product implementation",
            "product evidence population",
            "product-state validation",
            "product checkpoint creation",
            "evaluator change event",
            "post-change planning checkpoint creation",
            "first post-change product-code mutation",
            "post-change evidence population",
            "post-change product checkpoint creation",
            "first release-readiness evaluation",
            "release-readiness status",
            "repository defect",
            "documentation or discoverability defect",
            "machine-contract defect",
            "evaluation-methodology defect",
            "evaluator mistake",
            "environment limitation",
            "evidence-capture limitation",
            "PASS, FAIL, BLOCKED, or NOT TESTED",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)
        self.assertIn("planning/template evidence must not be reported as product evidence", self.text)
        self.assertIn("Deferred required browser proof keeps release readiness NOT READY", self.text)

    def test_protocol_requires_chronological_checkpoint_evidence(self) -> None:
        for phrase in (
            "chronology is part of lifecycle correctness",
            "planning checkpoint must exist before the first product-code mutation",
            "product checkpoint must exist before the first release-readiness evaluation",
            "does not retroactively repair lifecycle correctness",
            "Do not infer chronology from the final filesystem",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_protocol_requires_true_staged_disclosure(self) -> None:
        for phrase in (
            "Phase A — initial product only",
            "future requirement must not be visible before the evaluator change event",
            "prewritten list",
            "create the added requirement only after Phase A reaches its prerequisite product checkpoint",
            "Before that checkpoint, the requirement payload does not yet exist",
            "Evaluator Change Event",
            "Only after the Phase A product checkpoint exists may the evaluator create and disclose the additional requirement",
            "new requirement → re-plan/update planning authority → new planning checkpoint → product modification",
            "change event sent before the required Phase A product checkpoint is a chronology failure",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_protocol_forbids_retrospective_staged_chronology(self) -> None:
        for phrase in (
            "added requirement was visible before the event",
            "evaluation-methodology defect",
            "evaluator mistake",
            "first post-change product mutation",
            "post-change planning checkpoint",
            "final repository containing the new requirement",
            "Never infer staged chronology from the final filesystem",
            "NOT TESTED or BLOCKED",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_protocol_enforces_transcript_fallback_and_replay_isolation(self) -> None:
        for phrase in (
            "complete",
            "partial",
            "unavailable",
            "mark claims relying on the missing interval as NOT TESTED or BLOCKED rather than inferred PASS",
            "maintainer-controlled diagnostic environment",
            "Do not feed the clean-room model's report or artifacts into that replay",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)


if __name__ == "__main__":
    unittest.main()
