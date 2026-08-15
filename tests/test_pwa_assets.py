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
            self.assertEqual(icon["src"], "/icon.svg")
            self.assertEqual(icon["type"], "image/svg+xml")
            self.assertEqual(set(icon["purpose"].split()), {"any", "maskable"})

    def test_manifest_icon_paths_are_in_service_worker_static_assets(self) -> None:
        manifest = json.loads((ROOT / "assets/app.webmanifest").read_text(encoding="utf-8"))
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker)

        self.assertIsNotNone(match)
        static_assets = set(json.loads(match.group(1)))
        self.assertIn("/app.webmanifest", static_assets)
        self.assertLessEqual(
            {icon["src"] for icon in manifest["icons"]},
            static_assets,
        )

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
        self.assertIn('manifest.rel = "manifest"', registration)
        self.assertIn('manifest.href = manifestHref', registration)
        self.assertIn('navigator.serviceWorker.register("/service-worker.js", {', registration)
        self.assertIn('scope: "/"', registration)
        self.assertIn('updateViaCache: "none"', registration)
        self.assertIn("if (!registration.active)", registration)
        self.assertIn("await registration.update()", registration)
        self.assertIn('console.warn("Service worker registration failed", error)', registration)
        self.assertIn('console.warn("Service worker update check failed", error)', registration)

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
            self.assertIn(
                '<link rel="manifest" href="/app.webmanifest">',
                page_html,
            )
            self.assertIn(
                '<meta name="theme-color" content="#3f51b5">',
                page_html,
            )
            self.assertNotIn('rel="manifest"', preview_html)
            self.assertNotIn('name="theme-color"', preview_html)

    def test_conflicting_static_pwa_metadata_is_rejected(self) -> None:
        source = (
            "<html><head>"
            '<link rel="manifest" href="/other.webmanifest">'
            "</head><body></body></html>"
        )
        with self.assertRaises(finalize_site_metadata.SiteMetadataError):
            finalize_site_metadata.ensure_pwa_metadata(
                source,
                Path("index.html"),
            )

    def test_conflicting_or_duplicate_pwa_metadata_is_rejected(self) -> None:
        cases = {
            "conflicting theme color": '<meta name="theme-color" content="#000000">',
            "duplicate manifests": (
                '<link rel="manifest" href="/app.webmanifest">'
                '<link rel="manifest" href="/app.webmanifest">'
            ),
            "duplicate theme colors": (
                '<meta name="theme-color" content="#3f51b5">'
                '<meta name="theme-color" content="#3f51b5">'
            ),
        }
        for name, metadata in cases.items():
            with self.subTest(name=name):
                source = f"<html><head>{metadata}</head><body></body></html>"
                with self.assertRaises(finalize_site_metadata.SiteMetadataError):
                    finalize_site_metadata.ensure_pwa_metadata(
                        source,
                        Path("index.html"),
                    )

    def test_service_worker_keeps_documents_out_of_static_cache(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn('const CACHE_NAME = "templates-portal-shell-v3"', worker)
        self.assertIn(
            'const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"',
            worker,
        )
        self.assertIn(
            'const STATIC_ASSETS = ["/app.webmanifest", "/icon.svg"]',
            worker,
        )
        self.assertNotIn("const APP_SHELL", worker)
        self.assertNotIn('caches.match("/")', worker)
        for event in ("install", "activate", "message", "fetch"):
            self.assertIn(f'self.addEventListener("{event}"', worker)
        self.assertIn("function isDocumentRequest(request, url)", worker)
        self.assertIn('request.mode === "navigate"', worker)
        self.assertIn("if (isDocumentRequest(event.request, url))", worker)
        self.assertIn('fetch(request, { cache: "no-cache" })', worker)
        self.assertIn(
            "fetchFreshDocument(event.request).catch(() => offlineResponse())",
            worker,
        )
        self.assertEqual(worker.count("fetchFreshDocument(event.request)"), 1)
        self.assertIn("if (STATIC_ASSETS.includes(url.pathname))", worker)
        self.assertNotIn("caches.open(DOCUMENT_CACHE_NAME)", worker)

    def test_service_worker_classifies_instant_navigation_document_paths(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn('if (request.destination !== "")', worker)
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
        self.assertIn("try {", worker)
        self.assertIn("const cache = await caches.open(CACHE_NAME)", worker)
        self.assertIn("await cache.put(request, response.clone())", worker)
        self.assertIn('console.warn("PWA static asset cache refresh failed", error)', worker)
        self.assertIn("const refresh = refreshStaticAsset(event.request)", worker)
        self.assertIn("const cached = caches", worker)
        self.assertIn(".catch(() => undefined)", worker)
        self.assertIn("event.waitUntil(refresh.catch(() => undefined))", worker)
        self.assertIn("response || refresh", worker)
        self.assertNotIn("ignoreSearch", worker)

    def test_service_worker_activation_cache_cleanup_filter(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn(
            'key.startsWith("templates-portal-shell-") && key !== CACHE_NAME',
            worker,
        )
        self.assertIn("caches.delete(key)", worker)
        self.assertIn("self.clients.claim()", worker)
        self.assertNotIn(
            'key.startsWith("templates-portal-documents-")',
            worker,
        )

    def test_service_worker_exposes_freshness_capability_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        for state in (
            "verified-current",
            "checking",
            "cached-unverified",
            "update-available",
        ):
            self.assertIn(f'"{state}"', worker)
        self.assertIn('"templates:get-freshness-capabilities"', worker)
        self.assertIn('type: "templates:freshness-capabilities"', worker)
        self.assertIn('siteVersionUrl: "/site-version.json"', worker)
        self.assertIn("documentCacheName: DOCUMENT_CACHE_NAME", worker)

    def test_service_worker_offline_response_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn("function offlineResponse()", worker)
        self.assertIn("status: 503", worker)
        self.assertIn('statusText: "Service Unavailable"', worker)
        self.assertIn(
            'headers: { "Content-Type": "text/plain; charset=utf-8" }',
            worker,
        )

    def test_browser_regression_check_is_wired_into_visual_ci(self) -> None:
        workflow = (ROOT / ".github/workflows/mobile-visual-regression.yml").read_text(
            encoding="utf-8"
        )
        checker = (ROOT / "scripts/check_pwa_freshness.py").read_text(encoding="utf-8")

        self.assertIn("Check PWA freshness lifecycle", workflow)
        self.assertIn("python scripts/check_pwa_freshness.py", workflow)
        self.assertIn('service_workers="allow"', checker)
        self.assertIn('worker_source + "\\n" + marker', checker)
        self.assertIn("state.record_hit", checker)
        self.assertIn("navigator.serviceWorker.startMessages()", checker)
        self.assertIn("def _wait_for_manifest_version(", checker)
        self.assertIn("_wait_for_manifest_version(page, 2)", checker)
        self.assertIn('context.set_offline(True)', checker)
        self.assertIn('evidence["offline_fetch_status"] = 503', checker)
        self.assertIn('"document-v2"', checker)
        self.assertIn('"manifest-v{state.manifest_version}"', checker)
        self.assertIn("_wait_for_worker_version(page, 2)", checker)

    def test_pwa_freshness_checker_validates_missing_site_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            with self.assertRaises(check_pwa_freshness.PwaFreshnessError) as context:
                check_pwa_freshness.run_check(site_root, None)

        self.assertIn(
            "built site is missing required PWA assets",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
