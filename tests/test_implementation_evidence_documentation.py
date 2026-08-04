from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "TEMPLATE.md"


class ImplementationEvidenceDocumentationTests(unittest.TestCase):
    def test_template_requires_verified_negative_evidence_for_every_target(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "verified negative evidence for every target",
            source,
        )
        self.assertNotIn(
            "verified negative evidence wherever access, degraded behavior, failure, connectivity, or a breaking transition requires it",
            source,
        )


if __name__ == "__main__":
    unittest.main()
