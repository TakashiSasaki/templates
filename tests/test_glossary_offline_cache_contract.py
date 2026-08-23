from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "assets/service-worker.js"
RUNTIME = ROOT / "assets/javascripts/glossary-inline.js"
STYLE = ROOT / "assets/stylesheets/glossary-inline.css"


class GlossaryOfflineCacheContractTests(unittest.TestCase):
    def test_glossary_model_has_dedicated_cache_and_is_not_static_shell_content(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker)
        self.assertIsNotNone(match)
        static_assets = set(json.loads(match.group(1)))

        self.assertIn(
            'const GLOSSARY_CACHE_NAME = "templates-portal-glossary-v1";',
            worker,
        )
        self.assertIn('const GLOSSARY_MODEL_PATH = "/glossary/index.json";', worker)
        self.assertNotIn("/glossary/index.json", static_assets)
        self.assertIn("caches.open(GLOSSARY_CACHE_NAME)", worker)

    def test_glossary_capabilities_are_exposed_by_service_worker(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        self.assertIn("glossaryCacheName: GLOSSARY_CACHE_NAME", worker)
        self.assertIn("glossaryModelUrl: GLOSSARY_MODEL_PATH", worker)

    def test_glossary_fetch_route_precedes_document_and_static_routing(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        glossary_route = worker.index("if (url.pathname === GLOSSARY_MODEL_PATH)")
        document_route = worker.index("if (isDocumentRequest(event.request, url))")
        static_route = worker.index("if (STATIC_ASSETS.includes(url.pathname))")
        self.assertLess(glossary_route, document_route)
        self.assertLess(document_route, static_route)
        self.assertIn("respondWithGlossaryNetworkFirst(event)", worker)

    def test_glossary_model_uses_network_first_and_cached_fallback_only_on_failure(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn(
            "async function fetchGlossaryNetworkFirst(request, registerBackgroundTask)",
            worker,
        )
        self.assertIn('const response = await fetch(request, { cache: "no-cache" })', worker)
        self.assertIn("if (response.status >= 500)", worker)
        self.assertIn("(await cachedGlossaryFallback(request)) || response", worker)
        self.assertIn("const cached = await cachedGlossaryFallback(request)", worker)
        self.assertIn("throw error;", worker)
        self.assertNotIn("GLOSSARY_MODEL_PATH,\n  ...STATIC_ASSETS", worker)

    def test_authoritative_glossary_deletion_prevents_stale_fallback(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn("response.status === 404 || response.status === 410", worker)
        self.assertIn("authoritativeGlossaryDeletionGeneration = Math.max(", worker)
        self.assertIn("deleteCachedGlossaryModel(request, generation)", worker)
        self.assertIn("await caches.delete(GLOSSARY_CACHE_NAME)", worker)
        self.assertIn("if (authoritativeGlossaryDeletionGeneration > 0)", worker)

    def test_glossary_cache_mutations_and_deletions_are_generation_ordered(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn("let nextGlossaryRequestGeneration = 0;", worker)
        self.assertIn("let glossaryCacheMutationGeneration = 0;", worker)
        self.assertIn("let glossaryCacheMutationQueue = Promise.resolve();", worker)
        self.assertIn("function beginGlossaryRequest()", worker)
        self.assertIn("function recordAuthoritativeGlossaryDeletion(generation)", worker)
        self.assertIn("function enqueueGlossaryCacheMutation(generation, operation)", worker)
        self.assertGreaterEqual(
            worker.count("if (generation < glossaryCacheMutationGeneration)"),
            2,
        )
        self.assertIn("if (recordAuthoritativeGlossaryDeletion(generation))", worker)
        self.assertIn("glossaryCacheMutationGeneration = generation", worker)

    def test_cached_glossary_fallback_requires_freshness_aware_runtime_opt_in(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        runtime = RUNTIME.read_text(encoding="utf-8")

        self.assertIn(
            'const GLOSSARY_CACHED_ACCEPT_HEADER = "X-Templates-Glossary-Accepts-Cached";',
            worker,
        )
        self.assertIn(
            'if (request.headers.get(GLOSSARY_CACHED_ACCEPT_HEADER) !== "1")',
            worker,
        )
        self.assertIn(
            'const CACHED_ACCEPT_HEADER = "X-Templates-Glossary-Accepts-Cached";',
            runtime,
        )
        self.assertIn('headers: { [CACHED_ACCEPT_HEADER]: "1" }', runtime)

    def test_cached_glossary_response_is_marked_unverified_without_rewriting_json(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn("async function decorateCachedGlossaryModel(response, request)", worker)
        self.assertIn('headers.set("X-Templates-Freshness", "cached-unverified")', worker)
        self.assertIn('headers.set("Cache-Control", "no-store")', worker)
        self.assertIn("body = await response.arrayBuffer()", worker)
        self.assertNotIn("JSON.parse", worker)
        self.assertNotIn("JSON.stringify", worker)

    def test_cached_glossary_decoration_allows_missing_response_url(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        decorator = worker.split(
            "async function decorateCachedGlossaryModel(response, request)",
            1,
        )[1].split("async function cachedGlossaryFallback(request)", 1)[0]

        self.assertIn("if (response.status !== 200)", decorator)
        self.assertIn('response.headers.get("Content-Type")', decorator)
        self.assertIn("if (response.url && response.url !== request.url)", decorator)
        self.assertNotIn("isCacheableGlossaryResponse(response)", decorator)

    def test_cached_glossary_decoration_rejects_non_json_media_types(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        decorator = worker.split(
            "async function decorateCachedGlossaryModel(response, request)",
            1,
        )[1].split("async function cachedGlossaryFallback(request)", 1)[0]

        self.assertIn('contentType.includes("application/json")', decorator)
        self.assertIn('contentType.includes("+json")', decorator)
        self.assertIn("return undefined;", decorator)

    def test_glossary_runtime_surfaces_cached_unverified_state(self) -> None:
        runtime = RUNTIME.read_text(encoding="utf-8")
        stylesheet = STYLE.read_text(encoding="utf-8")

        self.assertIn('response.headers.get("X-Templates-Freshness")', runtime)
        self.assertIn('const CACHED_FRESHNESS = "cached-unverified";', runtime)
        self.assertIn("status.textContent = strings.cached_unverified;", runtime)
        self.assertNotIn("Saved glossary data · latest version not verified.", runtime)
        self.assertIn('class="glossary-inline-dialog__freshness"', runtime)
        self.assertIn("setFreshness(panel, freshness, strings)", runtime)
        self.assertIn('setFreshness(panel, "unavailable", strings)', runtime)
        self.assertIn(".glossary-inline-dialog__freshness", stylesheet)

    def test_cached_unverified_runtime_retries_network_on_later_activation(self) -> None:
        runtime = RUNTIME.read_text(encoding="utf-8")

        self.assertIn("if (freshness === CACHED_FRESHNESS) {", runtime)
        self.assertIn(
            "if (freshness === CACHED_FRESHNESS) {\n            glossaryPromise = undefined;\n          }",
            runtime,
        )

    def test_glossary_cache_version_cleanup_does_not_delete_document_cache(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn('key.startsWith("templates-portal-glossary-")', worker)
        self.assertIn("key !== GLOSSARY_CACHE_NAME", worker)
        self.assertNotIn('key.startsWith("templates-portal-documents-")', worker)


if __name__ == "__main__":
    unittest.main()
