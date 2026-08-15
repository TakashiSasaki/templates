from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaDocumentCacheReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

    def test_all_site_owned_runtime_javascript_is_precached(self) -> None:
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", self.worker)
        self.assertIsNotNone(match)
        static_assets = set(json.loads(match.group(1)))
        for name in (
            "glossary-inline.js",
            "guided-copy.js",
            "pwa.js",
            "repository-browser.js",
            "repository-tree-viewer.js",
        ):
            with self.subTest(name=name):
                self.assertIn(f"/javascripts/{name}", static_assets)

    def test_document_cache_mutations_are_serialized_per_exact_request_url(self) -> None:
        self.assertIn("const documentCacheMutationQueues = new Map()", self.worker)
        self.assertIn("function enqueueDocumentCacheMutation(request, operation)", self.worker)
        self.assertIn("const key = request.url", self.worker)
        self.assertIn("documentCacheMutationQueues.get(key) || Promise.resolve()", self.worker)
        self.assertIn("previous.catch(() => undefined).then(operation)", self.worker)
        self.assertIn("await enqueueDocumentCacheMutation(request, async () => {", self.worker)
        self.assertIn("await cache.put(request, cachedResponse)", self.worker)
        self.assertIn("await cache.delete(request)", self.worker)

    def test_redirected_cached_documents_fail_closed(self) -> None:
        self.assertIn("async function decorateCachedDocument(response, request)", self.worker)
        self.assertIn("response.url && response.url !== request.url", self.worker)
        self.assertIn('console.warn("PWA cached redirect fallback rejected"', self.worker)
        self.assertIn("return await decorateCachedDocument(response, request)", self.worker)

    def test_dotted_instant_navigation_paths_can_use_accept_header(self) -> None:
        self.assertIn('const accept = request.headers.get("Accept") || ""', self.worker)
        self.assertIn('accept.toLowerCase().includes("text/html")', self.worker)

    def test_malformed_response_urls_are_rejected_without_throwing(self) -> None:
        self.assertIn('console.warn("PWA document response URL is invalid", error)', self.worker)
        self.assertIn("new URL(response.url).origin !== self.location.origin", self.worker)


if __name__ == "__main__":
    unittest.main()
