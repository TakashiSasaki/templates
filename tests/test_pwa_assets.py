from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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

    def test_service_worker_limits_cache_to_the_root_shell(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn('const APP_SHELL = ["/", "/app.webmanifest", "/icon.svg"]', worker)
        for event in ("install", "activate", "fetch"):
            self.assertIn(f'self.addEventListener("{event}"', worker)
        self.assertIn('event.request.mode === "navigate"', worker)
        self.assertIn('caches.match("/")', worker)


if __name__ == "__main__":
    unittest.main()
