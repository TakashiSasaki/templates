from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "MAINTENANCE.md"


class LatestIndexNavigationIntegrationReviewTests(unittest.TestCase):
    def test_maintenance_documents_fragmented_uncataloged_source_fallback(self) -> None:
        maintenance = " ".join(
            MAINTENANCE.read_text(encoding="utf-8").split()
        ).casefold()
        self.assertIn(
            "fragment-free uncataloged regular-file targets resolve to the same immutable `/files/` snapshot",
            maintenance,
        )
        self.assertIn(
            "uncataloged regular-file targets with any fragment use the exact full-sha immutable github source",
            maintenance,
        )


if __name__ == "__main__":
    unittest.main()
