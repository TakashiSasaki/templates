from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaDocumentCacheReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.client = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")

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

    def test_document_cache_mutations_use_request_generation_order(self) -> None:
        self.assertIn("const documentCacheMutationQueues = new Map()", self.worker)
        self.assertIn("const documentCacheMutationGenerations = new Map()", self.worker)
        self.assertIn("let nextDocumentRequestGeneration = 0", self.worker)
        self.assertIn("function beginDocumentRequest()", self.worker)
        self.assertIn(
            "function enqueueDocumentCacheMutation(request, generation, operation)",
            self.worker,
        )
        self.assertIn("if (generation < appliedGeneration)", self.worker)
        self.assertIn("recordAuthoritativeDeletion(request, generation)", self.worker)
        self.assertIn("cacheVerifiedDocument(request, cachedResponse, generation)", self.worker)
        self.assertIn("deleteCachedDocument(request, generation)", self.worker)

    def test_authoritative_deletion_tombstone_blocks_stale_fallback(self) -> None:
        self.assertIn("const authoritativeDocumentDeletions = new Map()", self.worker)
        self.assertIn("authoritativeDocumentDeletions.set(key, generation)", self.worker)
        self.assertIn("authoritativeDocumentDeletions.has(request.url)", self.worker)
        self.assertIn("authoritativeDocumentDeletions.delete(request.url)", self.worker)

    def test_redirected_cached_documents_fail_closed(self) -> None:
        self.assertIn("async function decorateCachedDocument(response, request)", self.worker)
        self.assertIn("response.url && response.url !== request.url", self.worker)
        self.assertIn('console.warn("PWA cached redirect fallback rejected"', self.worker)
        self.assertIn("return await decorateCachedDocument(response, request)", self.worker)

    def test_cached_notice_is_inserted_after_an_unambiguous_body_open(self) -> None:
        self.assertIn("function injectCachedDocumentNotice(source)", self.worker)
        self.assertIn("source.matchAll(/<html\\b[^>]*>/gi)", self.worker)
        self.assertIn("source.matchAll(/<body\\b[^>]*>/gi)", self.worker)
        self.assertIn("source.matchAll(/<\\/body\\s*>/gi)", self.worker)
        self.assertIn("bodyOpenings.length !== 1", self.worker)
        self.assertIn('data-templates-cached-fallback="true"', self.worker)
        self.assertIn('id="templates-freshness-status-inline-style"', self.worker)
        self.assertIn("position:fixed", self.worker)
        self.assertIn("shiftedBodyOpeningEnd", self.worker)

    def test_commit_correlation_distinguishes_cached_and_network_representations(self) -> None:
        self.assertIn('type: "templates:document-commit"', self.worker)
        self.assertIn('representation,', self.worker)
        self.assertIn('requestGeneration: generation', self.worker)
        self.assertIn("let pendingDocumentCommit = null", self.client)
        self.assertIn('setPendingDocumentCommit(url, "cached", generation)', self.client)
        self.assertIn('setPendingDocumentCommit(data.url, "network", data.requestGeneration)', self.client)
        self.assertIn('pending.representation === "cached"', self.client)
        self.assertIn("preserveInitialEmbeddedCachedCommit", self.client)
        self.assertIn('dataset.templatesCachedFallback === "true"', self.client)
        self.assertIn("delete document.documentElement.dataset.templatesCachedFallback", self.client)

    def test_early_freshness_message_does_not_require_document_body(self) -> None:
        self.assertIn("const target = document.body || document.documentElement", self.client)
        self.assertIn("if (!target)", self.client)

    def test_sandbox_previews_are_not_pwa_document_surfaces(self) -> None:
        self.assertIn('url.pathname.startsWith("/repository-trees/previews/")', self.worker)
        preview_guard = self.worker.index('url.pathname.startsWith("/repository-trees/previews/")')
        navigate_branch = self.worker.index('request.mode === "navigate"')
        self.assertLess(preview_guard, navigate_branch)

    def test_dotted_instant_navigation_paths_can_use_accept_header(self) -> None:
        self.assertIn('const accept = request.headers.get("Accept") || ""', self.worker)
        self.assertIn('accept.toLowerCase().includes("text/html")', self.worker)

    def test_malformed_response_urls_are_rejected_without_throwing(self) -> None:
        self.assertIn('console.warn("PWA document response URL is invalid", error)', self.worker)
        self.assertIn("new URL(response.url).origin !== self.location.origin", self.worker)


if __name__ == "__main__":
    unittest.main()
