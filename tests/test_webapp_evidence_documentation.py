from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "docs"
    / "architecture"
    / "webapp-contracts.md"
)


class WebappEvidenceDocumentationTests(unittest.TestCase):
    def test_browser_identity_evidence_is_documented_as_current(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")

        self.assertIn("browser_identity/proof-family/browser-identity", text)
        self.assertIn("`browser` execution capability", text)
        self.assertIn("Planning mode applies the same proof-strength intent", text)
        self.assertNotIn("deferred to the browser/PWA evidence follow-up", text)


if __name__ == "__main__":
    unittest.main()
