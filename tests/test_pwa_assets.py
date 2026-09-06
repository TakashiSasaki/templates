from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_pwa_freshness  # noqa: E402
import finalize_site_metadata  # noqa: E402


class PwaAssetTests(unittest.TestCase):
    def test_manifest_has_minimum_installability_contract(self) -> None:
        manifest = json.loads((ROOT / "assets/app.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "/")
        self.assertTrue(manifest["name"])
        self.assertTrue(manifest["short_name"])
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        icons = manifest["icons"]
        for size in ("192x192", "512x512"):
            matching = [icon for icon in icons if icon.get("sizes") == size]
            self.assertEqual(len(matching), 1)
            icon = matching[0]
            self.assertEqual(icon["src"], f"/icon-{size.split('x')[0]}.png")
            self.assertEqual(icon["type"], "image/png")
            self.assertEqual(set(icon["purpose"].split()), {"any", "maskable"})

    def test_service_worker_precache_paths_exist_in_source_assets(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker)
        self.assertIsNotNone(match)
        static_assets = set(json.loads(match.group(1)))
        for public_path in static_assets:
            with self.subTest(public_path=public_path):
                self.assertTrue(
                    (ROOT / "assets" / public_path.lstrip("/")).is_file(),
                    f"missing source asset for {public_path}",
                )
        manifest = json.loads((ROOT / "assets/app.webmanifest").read_text(encoding="utf-8"))
        self.assertIn("/app.webmanifest", static_assets)
        self.assertLessEqual({icon["src"] for icon in manifest["icons"]}, static_assets)
        self.assertIn("/site-chrome-locales.json", static_assets)
        self.assertIn("/stylesheets/freshness-status.css", static_assets)
        self.assertIn("/javascripts/pwa.js", static_assets)

    def test_svg_icon_is_self_contained_and_scalable(self) -> None:
        icon_path = ROOT / "assets/icon.svg"
        icon_text = icon_path.read_text(encoding="utf-8")
        icon = ET.fromstring(icon_text)
        self.assertEqual(icon.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(icon.attrib["viewBox"], "0 0 512 512")
        self.assertNotIn("<script", icon_text.casefold())
        self.assertNotIn("http://", icon_text.replace("http://www.w3.org/2000/svg", ""))
        self.assertNotIn("https://", icon_text)

    def test_zensical_uses_the_svg_as_favicon_and_loads_registration(self) -> None:
        config = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        registration = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")
        self.assertIn('favicon = "icon.svg"', config)
        self.assertIn('"javascripts/pwa.js"', config)
        self.assertIn('"stylesheets/freshness-status.css"', config)
        self.assertIn('manifest.rel = "manifest"', registration)
        self.assertIn('manifest.href = manifestHref', registration)
        self.assertIn('navigator.serviceWorker.register("/service-worker.js", {', registration)
        self.assertIn('scope: "/"', registration)
        self.assertIn('updateViaCache: "none"', registration)
        self.assertIn("if (!registration.active)", registration)
        self.assertIn("await registration.update()", registration)
        self.assertIn('console.warn("Service worker registration failed", error)', registration)
        self.assertIn('console.warn("Service worker update check failed", error)', registration)

    def test_registration_applies_freshness_states_and_clears_only_after_commit(self) -> None:
        registration = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")
        self.assertIn('data?.type !== "templates:freshness-state"', registration)
        self.assertIn("applyFreshnessState(data)", registration)
        self.assertIn("lastFreshnessGeneration", registration)
        for state in ("checking", "cached-unverified", "update-available", "verified-current"):
            self.assertIn(f'"{state}"', registration)
        self.assertIn("pendingDocumentCommit", registration)
        self.assertIn("lastCommitGeneration", registration)
        self.assertIn("globalThis.document$", registration)
        self.assertIn("documentObservable.subscribe(handleCommittedDocument)", registration)
        self.assertIn("committedUrl === pending.url", registration)
        self.assertIn('pending.representation === "cached"', registration)
        self.assertIn('status.id = freshnessStatusId', registration)
        self.assertIn('document.body || document.documentElement', registration)
        self.assertIn('document.getElementById(freshnessStatusId)?.remove()', registration)
        self.assertIn('const acknowledgementPort = event.ports?.[0]', registration)
        self.assertIn('type: "templates:freshness-state-applied"', registration)
        self.assertIn('type === "templates:document-commit"', registration)
        self.assertIn('type: "templates:get-current-freshness-state"', registration)
        self.assertIn("requestCurrentFreshnessState()", registration)
        self.assertIn('const siteChromeLocalesHref = "/site-chrome-locales.json"', registration)
        self.assertIn("async function loadSiteChromeLocales()", registration)
        self.assertIn("document.documentElement?.lang", registration)
        self.assertIn("const applied = await applyFreshnessState(data)", registration)
        self.assertIn("strings.saved_copy", registration)
        self.assertIn("strings.reload", registration)
        self.assertNotIn('label.textContent = "Saved copy."', registration)
        self.assertNotIn('reload.textContent = "Reload"', registration)

    def test_generated_pages_receive_static_pwa_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            preview_root = site_root / "repository-trees/previews/skill/revision"
            preview_root.mkdir(parents=True)
            page = site_root / "index.html"
            preview = preview_root / "preview.html"
            source = "<html><head><title>Page</title></head><body></body></html>"
            page.write_text(source, encoding="utf-8")
            preview.write_text(source, encoding="utf-8")
            canonical_count, pwa_count = finalize_site_metadata.normalize_site_metadata(
                site_root,
                "https://templates.moukaeritai.work/",
            )
            self.assertEqual(canonical_count, 2)
            self.assertEqual(pwa_count, 1)
            page_html = page.read_text(encoding="utf-8")
            preview_html = preview.read_text(encoding="utf-8")
            self.assertIn('<link rel="manifest" href="/app.webmanifest">', page_html)
            self.assertIn('<meta name="theme-color" content="#3f51b5">', page_html)
            self.assertNotIn('rel="manifest"', preview_html)
            self.assertNotIn('name="theme-color"', preview_html)

    def test_conflicting_static_pwa_metadata_is_rejected(self) -> None:
        source = "<html><head><link rel=\"manifest\" href=\"/other.webmanifest\"></head><body></body></html>"
        with self.assertRaises(finalize_site_metadata.SiteMetadataError):
            finalize_site_metadata.ensure_pwa_metadata(source, Path("index.html"))

    def test_conflicting_or_duplicate_pwa_metadata_is_rejected(self) -> None:
        cases = {
            "conflicting theme color": '<meta name="theme-color" content="#000000">',
            "duplicate manifests": '<link rel="manifest" href="/app.webmanifest"><link rel="manifest" href="/app.webmanifest">',
            "duplicate theme colors": '<meta name="theme-color" content="#3f51b5"><meta name="theme-color" content="#3f51b5">',
        }
        for name, metadata in cases.items():
            with self.subTest(name=name):
                source = f"<html><head>{metadata}</head><body></body></html>"
                with self.assertRaises(finalize_site_metadata.SiteMetadataError):
                    finalize_site_metadata.ensure_pwa_metadata(source, Path("index.html"))

    def test_service_worker_uses_separate_shell_and_document_caches(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn('const CACHE_NAME = "templates-portal-shell-v4"', worker)
        self.assertIn('const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"', worker)
        self.assertNotIn("const APP_SHELL", worker)
        self.assertNotIn('caches.match("/")', worker)
        for event in ("install", "activate", "message", "fetch"):
            self.assertIn(f'self.addEventListener("{event}"', worker)
        self.assertIn("function isDocumentRequest(request, url)", worker)
        self.assertIn('request.mode === "navigate"', worker)
        self.assertIn("if (isDocumentRequest(event.request, url))", worker)
        self.assertIn('fetch(request, { cache: "no-cache" })', worker)
        self.assertIn("respondWithDocumentNetworkFirst(event)", worker)
        self.assertIn("caches.open(DOCUMENT_CACHE_NAME)", worker)

    def test_service_worker_document_network_first_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn(
            "async function fetchDocumentNetworkFirst(event, registerBackgroundTask)",
            worker,
        )
        self.assertIn("function respondWithDocumentNetworkFirst(event)", worker)
        self.assertIn("const generation = beginDocumentRequest()", worker)
        self.assertIn("const networkOutcomePromise = startDocumentNetworkRequest(event.request)", worker)
        self.assertIn("softTimeoutSignal()", worker)
        self.assertIn("if (response.status === 404 || response.status === 410)", worker)
        self.assertIn("recordAuthoritativeDeletion(request, generation)", worker)
        self.assertIn("deleteCachedDocument(request, generation)", worker)
        self.assertIn("await caches.delete(DOCUMENT_CACHE_NAME)", worker)
        self.assertIn("if (response.status >= 500)", worker)
        self.assertIn("cachedDocumentFallback(", worker)
        self.assertIn("isCacheableDocumentResponse(response)", worker)
        self.assertIn("response.status !== 200", worker)
        self.assertIn('includes("text/html")', worker)
        self.assertIn("cacheVerifiedDocument(request, response.clone(), generation)", worker)
        self.assertIn("const lifetimePromise = responsePromise", worker)
        self.assertIn("event.waitUntil(lifetimePromise)", worker)
        self.assertIn("event.respondWith(responsePromise)", worker)
        self.assertIn("await cache.put(request, cachedResponse)", worker)
        self.assertIn("await cache.delete(request)", worker)
        self.assertLess(
            worker.index("event.waitUntil(lifetimePromise)"),
            worker.index("self.addEventListener(\"fetch\""),
        )
        self.assertNotIn(
            "event.waitUntil(cacheVerifiedDocument(request, cachedResponse, generation))",
            worker,
        )

    def test_cached_document_fallback_is_explicitly_marked_by_state(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        stylesheet = (ROOT / "assets/stylesheets/freshness-status.css").read_text(encoding="utf-8")
        self.assertIn('id="templates-freshness-status"', worker)
        self.assertIn('data-freshness-state="${state}"', worker)
        self.assertIn('const SITE_CHROME_LOCALES_PATH = "/site-chrome-locales.json"', worker)
        self.assertIn("const model = await loadSiteChromeLocales()", worker)
        self.assertIn("const language = htmlLanguage(source)", worker)
        self.assertIn("freshnessNoticeHtml(state, strings)", worker)
        self.assertIn("injectCachedDocumentNotice(source, state, strings)", worker)
        self.assertNotIn("Checking for the latest version…", worker)
        self.assertNotIn("The latest version could not be verified.", worker)
        self.assertIn('headers.set("X-Templates-Freshness", state)', worker)
        self.assertIn('headers.set("Cache-Control", "no-store")', worker)
        for header in ("Content-Encoding", "Content-Length", "ETag", "Last-Modified"):
            self.assertIn(f'"{header}"', worker)
        self.assertIn('state !== "checking" && state !== "cached-unverified"', worker)
        self.assertIn("bodyClosures.length !== 1", worker)
        self.assertIn('id="templates-freshness-status-inline-style"', worker)
        self.assertIn("position: fixed", stylesheet)
        self.assertIn("inset-block-start: 0", stylesheet)

    def test_instant_navigation_cached_fallback_requires_ui_acknowledgement(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn("async function postFreshnessState(", worker)
        self.assertIn("async function publishFreshnessState(", worker)
        self.assertIn("new MessageChannel()", worker)
        self.assertIn("FRESHNESS_UI_ACK_TIMEOUT_MS", worker)
        self.assertIn('type === "templates:freshness-state-applied"', worker)
        self.assertIn('url: event.request.url', worker)
        self.assertIn('requestGeneration: generation', worker)
        self.assertIn('"checking",\n      generation,\n      true', worker)

        start = worker.index("async function fallbackForCompletedFailure")
        end = worker.index("async function handleCompletedDocumentNetwork", start)
        fallback = worker[start:end]
        navigation_start = fallback.index('if (event.request.mode === "navigate")')
        acknowledgement_start = fallback.index("const acknowledged = await publishFreshnessState(")
        self.assertIn(
            'rememberFreshnessState(event, "cached-unverified", generation)',
            fallback[navigation_start:acknowledgement_start],
        )
        self.assertIn(
            '"cached-unverified",\n    generation,\n    true',
            fallback[acknowledgement_start:],
        )

    def test_service_worker_classifies_instant_navigation_document_paths(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn('url.pathname.startsWith("/repository-trees/previews/")', worker)
        self.assertIn('if (request.destination !== "")', worker)
        self.assertIn('const accept = request.headers.get("Accept") || ""', worker)
        self.assertIn('accept.toLowerCase().includes("text/html")', worker)
        self.assertIn('pathname.endsWith("/") || pathname.endsWith(".html")', worker)
        self.assertIn('pathname.slice(pathname.lastIndexOf("/") + 1)', worker)
        self.assertIn('!lastSegment.includes(".")', worker)
        self.assertIn('url.origin !== self.location.origin', worker)
        self.assertIn('event.request.method !== "GET"', worker)

    def test_service_worker_static_asset_cache_revalidates_exact_keys(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn("async function refreshStaticAsset(request)", worker)
        self.assertIn('const response = await fetch(request, { cache: "no-cache" })', worker)
        self.assertIn("if (response.ok)", worker)
        self.assertIn("const cache = await caches.open(CACHE_NAME)", worker)
        self.assertIn("await cache.put(request, response.clone())", worker)
        self.assertIn('console.warn("PWA static asset cache refresh failed", error)', worker)
        self.assertIn("const refresh = refreshStaticAsset(event.request)", worker)
        self.assertIn("event.waitUntil(refresh.catch(() => undefined))", worker)
        self.assertIn("response || refresh", worker)
        self.assertNotIn("ignoreSearch", worker)

    def test_service_worker_activation_cleanup_preserves_document_cache(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn('key.startsWith("templates-portal-shell-")', worker)
        self.assertIn("key !== CACHE_NAME", worker)
        self.assertIn("caches.delete(key)", worker)
        self.assertIn("self.clients.claim()", worker)
        self.assertNotIn('key.startsWith("templates-portal-documents-")', worker)

    def test_service_worker_exposes_freshness_capability_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        for state in ("verified-current", "checking", "cached-unverified", "update-available"):
            self.assertIn(f'"{state}"', worker)
        self.assertIn('"templates:get-freshness-capabilities"', worker)
        self.assertIn('type: "templates:freshness-capabilities"', worker)
        self.assertIn('siteVersionUrl: "/site-version.json"', worker)
        self.assertIn("documentCacheName: DOCUMENT_CACHE_NAME", worker)
        self.assertIn("softTimeoutMs: DOCUMENT_SOFT_TIMEOUT_MS", worker)
        self.assertIn("const DOCUMENT_SOFT_TIMEOUT_MS = 1500", worker)

    def test_service_worker_cache_miss_offline_response_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn("async function offlineResponse(request)", worker)
        self.assertIn("const language = requestLanguage(model, request)", worker)
        self.assertIn("strings?.offline_unavailable", worker)
        self.assertIn("status: 503", worker)
        self.assertIn('statusText: "Service Unavailable"', worker)
        self.assertIn('headers: { "Content-Type": "text/plain; charset=utf-8" }', worker)

    def test_browser_regression_check_is_wired_into_visual_ci(self) -> None:
        workflow = (ROOT / ".github/workflows/mobile-visual-regression.yml").read_text(encoding="utf-8")
        checker = (ROOT / "scripts/check_pwa_freshness.py").read_text(encoding="utf-8")
        self.assertIn("Check PWA freshness lifecycle", workflow)
        self.assertIn("python scripts/check_pwa_freshness.py", workflow)
        self.assertIn("Check PWA slow-network convergence", workflow)
        self.assertIn("python scripts/check_pwa_slow_convergence.py", workflow)
        self.assertIn('service_workers="allow"', checker)
        self.assertIn('worker_source + "\\n" + marker', checker)
        self.assertIn("state.record_hit", checker)
        self.assertIn("navigator.serviceWorker.startMessages()", checker)
        self.assertIn("def _wait_for_manifest_version(", checker)
        self.assertIn("_wait_for_manifest_version(page, 2)", checker)
        self.assertIn('context.set_offline(True)', checker)
        self.assertIn('evidence["offline_cached_status"] = 200', checker)
        self.assertIn('evidence["offline_cache_miss_status"] = 503', checker)
        self.assertIn('evidence["legacy_instant_navigation_status"] = 503', checker)
        self.assertIn('evidence["network_fetch_preserved_indicator_until_commit"] = True', checker)
        self.assertIn('evidence["committed_navigation_cleared_indicator"] = True', checker)
        self.assertIn('"document-v2"', checker)
        self.assertIn('"manifest-v{state.manifest_version}"', checker)
        self.assertIn("_wait_for_worker_version(page, 2)", checker)

    def test_pwa_freshness_checker_validates_missing_site_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            with self.assertRaises(check_pwa_freshness.PwaFreshnessError) as context:
                check_pwa_freshness.run_check(site_root, None)
        self.assertIn("built site is missing required PWA assets", str(context.exception))


if __name__ == "__main__":
    unittest.main()
