from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "docs"
    / "architecture"
    / "webapp-contracts.md"
)


class WebappEvidenceDocumentationTests(unittest.TestCase):
    def test_browser_identity_evidence_is_documented_as_current_not_deferred(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertNotIn(
            "Browser-identity executable proof is intentionally deferred",
            text,
        )
        self.assertIn(
            "browser_identity/proof-family/browser-identity",
            text,
        )
        self.assertIn(
            "browser-level positive and negative proof backed by a command that declares browser execution capability",
            text,
        )
        self.assertIn(
            "PWA installability, application-icon, offline/freshness, and update evidence are owned separately by `capability.pwa`",
            text,
        )


if __name__ == "__main__":
    unittest.main()
