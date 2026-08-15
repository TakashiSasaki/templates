from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaFreshReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.client = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")

    def test_uncached_authoritative_miss_does_not_purge_document_namespace(self) -> None:
        self.assertIn("await deleteCachedDocument(request, generation);", self.worker)
        self.assertNotIn("deleted === false", self.worker)
        self.assertIn(
            'console.warn("PWA authoritative document cache deletion failed", error)',
            self.worker,
        )
        self.assertIn("await caches.delete(DOCUMENT_CACHE_NAME);", self.worker)

    def test_document_event_without_network_commit_cannot_clear_stale_warning(self) -> None:
        handler_start = self.client.index("function handleCommittedDocument()")
        handler_end = self.client.index("\n\n  if (!document.querySelector", handler_start)
        handler = self.client[handler_start:handler_end]
        self.assertIn('pending.representation === "cached"', handler)
        self.assertIn("clearFreshnessStatus();", handler)
        self.assertEqual(handler.count("clearFreshnessStatus();"), 1)
        self.assertTrue(handler.rstrip().endswith("clearInitialCachedMarker();\n  }"))


if __name__ == "__main__":
    unittest.main()
