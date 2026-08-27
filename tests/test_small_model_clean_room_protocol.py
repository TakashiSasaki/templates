from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "examples/evaluations/small-model-clean-room-protocol.md"


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
            self.assertIn(phrase, self.text)
        self.assertIn("current maintenance conversation must never be described as a clean-room run", self.text)

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
            self.assertIn(phrase, self.text)

    def test_protocol_separates_lifecycle_and_attribution(self) -> None:
        for phrase in (
            "scaffold validation",
            "product implementation",
            "product evidence population",
            "product-state validation",
            "release-readiness status",
            "repository defect",
            "environment limitation",
            "evidence-capture limitation",
            "PASS, FAIL, BLOCKED, or NOT TESTED",
        ):
            self.assertIn(phrase, self.text)
        self.assertIn("planning/template evidence must not be reported as product evidence", self.text)
        self.assertIn("Deferred required browser proof keeps release readiness NOT READY", self.text)


if __name__ == "__main__":
    unittest.main()
