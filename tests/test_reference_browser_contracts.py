"""Mutation regressions for the Site adapter's consumption of public contracts."""
import copy
import json
import unittest
from pathlib import Path
from scripts.check_reference_website import check_link, check_manifest, viewport_probes

ROOT = Path(__file__).resolve().parents[1]


class Links:
    def __init__(self, hrefs):
        self.hrefs = hrefs
    def count(self):
        return len(self.hrefs)
    def nth(self, index):
        return Links([self.hrefs[index]])
    def get_attribute(self, name):
        assert name == "href"
        return self.hrefs[0]


class Page:
    url = "https://example.test/"
    def locator(self, selector):
        assert selector == 'link[rel="icon"]'
        return Links(["/icon.svg"])


class ReferenceBrowserContractTests(unittest.TestCase):
    def test_identity_change_requires_product_change(self):
        expected = json.loads((ROOT / "contracts/browser-identity.json").read_text())["favicon"]
        check_link(Page(), expected)
        expected["href"] = "/different.svg"
        with self.assertRaises(AssertionError):
            check_link(Page(), expected)

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
