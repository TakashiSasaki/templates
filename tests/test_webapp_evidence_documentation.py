from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "docs"
    / "architecture"
)
WEBAPP_CONTRACTS = ARCHITECTURE / "webapp-contracts.md"
VALIDATION_TOOLCHAIN = ARCHITECTURE / "validation-toolchain.md"


class WebappEvidenceDocumentationTests(unittest.TestCase):
    def test_browser_identity_evidence_is_documented_as_current_not_deferred(self) -> None:
        contracts = WEBAPP_CONTRACTS.read_text(encoding="utf-8")
        toolchain = VALIDATION_TOOLCHAIN.read_text(encoding="utf-8")

        self.assertNotIn(
            "Browser-identity executable proof is intentionally deferred",
            contracts,
        )
        self.assertNotIn(
            "executable proof that the declared favicon is actually emitted and served is intentionally introduced with the subsequent browser/PWA evidence layer",
            toolchain,
        )
        self.assertIn(
            "browser_identity/proof-family/browser-identity",
            contracts,
        )
        self.assertIn(
            "browser-level positive and negative proof backed by a command that declares browser execution capability",
            contracts,
        )
        self.assertIn(
            "Browser identity is not satisfied by the `browser-identity.json` declaration alone",
            toolchain,
        )
        self.assertIn(
            "positive and negative browser-level proof backed by an authoritative command whose execution capabilities include `browser`",
            toolchain,
        )
        self.assertIn(
            "PWA installability, application-icon, offline/freshness, and update evidence are owned separately by `capability.pwa`",
            contracts,
        )
        self.assertIn(
            "PWA installability, application-icon, offline/freshness, and update proof families remain separately owned by `capability.pwa`",
            toolchain,
        )


if __name__ == "__main__":
    unittest.main()
