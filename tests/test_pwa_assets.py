from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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
        self.assertIn('register("/service-worker.js", { scope: "/" })', registration)

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

        self.assertIn('const CACHE_NAME = "templates-portal-shell-v2"', worker)
        self.assertIn(
            'const STATIC_ASSETS = ["/app.webmanifest", "/icon.svg"]',
            worker,
        )
        self.assertNotIn("const APP_SHELL", worker)
        self.assertNotIn('caches.match("/")', worker)
        for event in ("install", "activate", "fetch"):
            self.assertIn(f'self.addEventListener("{event}"', worker)
        self.assertIn('event.request.mode === "navigate"', worker)
        self.assertIn(
            "fetch(event.request).catch(() => offlineResponse())",
            worker,
        )
        self.assertIn("if (STATIC_ASSETS.includes(url.pathname))", worker)

    def test_service_worker_static_asset_cache_ignores_query_string(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn("caches.open(CACHE_NAME)", worker)
        self.assertIn(
            "cache.match(event.request, { ignoreSearch: true })",
            worker,
        )

    def test_service_worker_activation_cache_cleanup_filter(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn(
            'key.startsWith("templates-portal-shell-") && key !== CACHE_NAME',
            worker,
        )
        self.assertIn("caches.delete(key)", worker)
        self.assertIn("self.clients.claim()", worker)

    def test_service_worker_offline_response_contract(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn("function offlineResponse()", worker)
        self.assertIn("status: 503", worker)
        self.assertIn('statusText: "Service Unavailable"', worker)
        self.assertIn(
            'headers: { "Content-Type": "text/plain; charset=utf-8" }',
            worker,
        )


if __name__ == "__main__":
    unittest.main()
