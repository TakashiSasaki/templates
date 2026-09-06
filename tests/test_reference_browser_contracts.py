"""Mutation regressions for the Site adapter's consumption of public contracts."""
import copy
import json
import unittest
from pathlib import Path

from scripts.check_reference_website import check_link, check_manifest, viewport_probes
from scripts.render_website_metadata import normalize_link_relation

ROOT = Path(__file__).resolve().parents[1]


class Links:
    def __init__(self, links):
        self.links = links

    def count(self):
        return len(self.links)

    def nth(self, index):
        return Links([self.links[index]])

    def get_attribute(self, name):
        return self.links[0].get(name)


class Page:
    url = "https://example.test/"

    def __init__(self, links=None):
        self.links = links or {
            "icon": [
                {
                    "href": "/icon.svg",
                    "type": "image/svg+xml",
                    "sizes": "any",
                }
            ]
        }

    def locator(self, selector):
        relation = selector.split('"')[1]
        return Links(self.links.get(relation, []))


class ReferenceBrowserContractTests(unittest.TestCase):
    def test_identity_change_requires_product_change(self):
        expected = json.loads((ROOT / "contracts/browser-identity.json").read_text())["favicon"]
        check_link(Page(), expected)
        for field, value in (
            ("href", "/different.svg"),
            ("mediaType", "image/png"),
            ("sizes", ["32x32"]),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(expected)
                changed[field] = value
                with self.assertRaises(AssertionError):
                    check_link(Page(), changed)

    def test_fallback_identity_compares_its_own_declared_metadata(self):
        fallback = {
            "relation": "icon",
            "href": "/icon-32.png",
            "mediaType": "image/png",
            "sizes": ["64x64", "32x32"],
        }
        page = Page({
            "icon": [
                {
                    "href": "/icon.svg",
                    "type": "image/svg+xml",
                    "sizes": "any",
                },
                {
                    "href": "/icon-32.png",
                    "type": "image/png",
                    "sizes": "32x32 64x64",
                },
            ]
        })
        check_link(page, fallback)
        for field, value in (
            ("mediaType", "image/webp"),
            ("sizes", ["16x16"]),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(fallback)
                changed[field] = value
                with self.assertRaises(AssertionError):
                    check_link(page, changed)

    def test_site_renderer_normalizes_declared_link_identity_fields(self):
        path = Path("index.html")
        source = (
            '<html><head>'
            '<link rel="icon" href="./icon.svg">'
            '<link rel="apple-touch-icon" href="/icon-180.png" sizes="180x180">'
            '</head><body></body></html>'
        )
        favicon = json.loads((ROOT / "contracts/browser-identity.json").read_text())["favicon"]
        ios = json.loads((ROOT / "contracts/pwa-manifest.json").read_text())[
            "platformCompatibility"
        ]["ios"]["homeScreenIcon"]
        source = normalize_link_relation(
            source,
            favicon["relation"],
            [favicon],
            path,
        )
        source = normalize_link_relation(
            source,
            ios["relation"],
            [ios],
            path,
        )
        self.assertIn(
            '<link rel="icon" href="/icon.svg" type="image/svg+xml" sizes="any">',
            source,
        )
        self.assertIn(
            '<link rel="apple-touch-icon" href="/icon-180.png" type="image/png" sizes="180x180">',
            source,
        )
        self.assertNotIn('href="./icon.svg"', source)

    def test_every_declared_breakpoint_is_probed(self):
        expected = json.loads((ROOT / "contracts/viewports.json").read_text())
        expected["viewports"].append({"id":"wide", "minWidthPx":1536, "description":"Wide layout"})
        self.assertIn(1536, viewport_probes(expected))
        self.assertNotIn(0, viewport_probes(expected))

    def test_manifest_semantics_cannot_drift_behind_asset_presence(self):
        expected = json.loads((ROOT / "contracts/pwa-manifest.json").read_text())
        actual = json.loads((ROOT / "assets/app.webmanifest").read_text())
        routes = {r["id"]: r["path"] for r in json.loads((ROOT / "contracts/routes.json").read_text())["routes"]}
        url = "https://example.test/app.webmanifest"
        check_manifest(actual, expected, routes, url)
        for field, value in [("orientation","portrait"),("start_url","/wrong/"),("scope","/wrong/")]:
            with self.subTest(field=field):
                changed = copy.deepcopy(actual)
                changed[field] = value
                with self.assertRaises(AssertionError):
                    check_manifest(changed, expected, routes, url)
        for field, value in [("sizes","1x1"),("purpose","any"),("type","text/plain")]:
            with self.subTest(icon_field=field):
                changed = copy.deepcopy(actual)
                changed["icons"][1][field] = value
                with self.assertRaises(AssertionError):
                    check_manifest(changed, expected, routes, url)

    def test_japanese_entry_links_to_generated_localized_anchor(self):
        landing = (ROOT / "translations/ja/docs/landing.md").read_text()
        target = '/ja/coexistence/#self-hosting-reference-consumer'
        self.assertEqual(landing.count('href="' + target + '"'), 2)
        from scripts.render_reference_consumer import outputs
        self.assertIn('id="self-hosting-reference-consumer"', outputs(ROOT)["translations/ja/docs/policy-composition-coexistence.md"])


if __name__ == "__main__":
    unittest.main()
