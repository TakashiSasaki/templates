from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_DIR = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "docs"
    / "architecture"
)


class WebappEvidenceDocumentationTests(unittest.TestCase):
    def read_document(self, name: str) -> str:
        return (ARCHITECTURE_DIR / name).read_text(encoding="utf-8")

    def test_browser_identity_evidence_is_documented_as_current(self) -> None:
        contracts = self.read_document("webapp-contracts.md")
        boundaries = self.read_document("responsibility-boundaries.md")
        toolchain = self.read_document("validation-toolchain.md")

        self.assertIn("browser_identity/proof-family/browser-identity", contracts)
        self.assertIn("`browser` execution capability", contracts)
        self.assertIn("Planning mode applies the same proof-strength intent", contracts)

        self.assertIn("browser_identity/proof-family/browser-identity", boundaries)
        self.assertIn("browser-backed executable proof", boundaries)
        self.assertIn("browser_identity/proof-family/browser-identity", toolchain)
        self.assertIn("browser-backed executable proof", toolchain)
        self.assertIn(
            "positive and negative browser-level proof backed by an authoritative command whose execution capabilities include `browser`",
            toolchain,
        )

        self.assertIn(
            "PWA installability, application-icon, offline/freshness, and update evidence are owned separately by `capability.pwa`",
            contracts,
        )
        self.assertIn(
            "`capability.pwa` owns its installability, application-icon, offline/freshness, and update proof families",
            boundaries,
        )
        self.assertIn(
            "PWA installability, application-icon, offline/freshness, and update proof families remain separately owned by `capability.pwa`",
            toolchain,
        )

        combined = "\n".join((contracts, boundaries, toolchain))
        for obsolete in (
            "deferred to the browser/PWA evidence follow-up",
            "introduced separately with the browser/PWA proof layer",
            "introduced with the subsequent browser/PWA evidence layer",
        ):
            self.assertNotIn(obsolete, combined)


if __name__ == "__main__":
    unittest.main()
