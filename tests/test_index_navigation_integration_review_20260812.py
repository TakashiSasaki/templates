from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
PUBLIC_URL_BOUNDARY_CHECKER = ROOT / "scripts/check_public_url_boundary.py"
POLICY = ROOT / "PUBLISHING.md"


class CurrentIndexNavigationIntegrationReviewTests(unittest.TestCase):
    def test_guided_retired_url_boundary_checks_url_attributes_not_visible_prose(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        checker = PUBLIC_URL_BOUNDARY_CHECKER.read_text(encoding="utf-8")
        self.assertIn("scripts/check_public_url_boundary.py", workflow)
        self.assertIn('relative.parts[0] == "guided"', checker)
        self.assertIn("return browser_source_view or guided_view", checker)

    def test_fragmented_uncataloged_files_use_immutable_source_fallback(self) -> None:
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())
        self.assertNotIn("representable `L<number>` line fragment", policy)
        self.assertIn(
            "an uncataloged regular tracked file with any fragment opens the exact full-SHA immutable GitHub source",
            policy,
        )

    def test_nested_guided_urls_are_current_projection_not_immutable_identity(self) -> None:
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())
        self.assertIn(
            "Nested guided-index URLs identify the current reviewed provider/path projection",
            policy,
        )
        self.assertIn(
            "the exact provider revision is recorded in the guided page and graph rather than encoded in that nested URL",
            policy,
        )


if __name__ == "__main__":
    unittest.main()
