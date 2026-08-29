from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "components" / "artifact.webapp-core"
FILES = WEBAPP / "files"


class WebappBrowserIdentityTests(unittest.TestCase):
    def load_json(self, relative: str) -> dict:
        return json.loads((FILES / relative).read_text(encoding="utf-8"))

    def test_browser_identity_is_registered_as_webapp_authority(self) -> None:
        descriptor = json.loads((WEBAPP / "component.json").read_text(encoding="utf-8"))
        registrations = {
            item["id"]: item for item in descriptor["contract_registrations"]
        }
        registration = registrations["browser_identity"]
        self.assertEqual(registration["document"], "contracts/browser-identity.json")
        self.assertEqual(registration["schema"], "schemas/browser-identity.schema.json")
        self.assertEqual(registration["document_schema_version"], 1)

    def test_seed_uses_the_standard_icon_relationship_and_svg_preference(self) -> None:
        document = self.load_json("contracts/browser-identity.json")
        self.assertEqual(document["favicon"]["relation"], "icon")
        self.assertEqual(document["favicon"]["mediaType"], "image/svg+xml")
        self.assertEqual(document["favicon"]["sizes"], ["any"])

    def test_schema_rejects_nonstandard_relationship_but_allows_raster_icons(self) -> None:
        schema = self.load_json("schemas/browser-identity.schema.json")
        seed = self.load_json("contracts/browser-identity.json")
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(seed)), [])

        invalid = copy.deepcopy(seed)
        invalid["favicon"]["relation"] = "shortcut icon"
        self.assertTrue(list(validator.iter_errors(invalid)))

        raster = copy.deepcopy(seed)
        raster["favicon"] = {
            "relation": "icon",
            "href": "favicon.png",
            "mediaType": "image/png",
            "sizes": ["32x32"],
            "fallbacks": [],
        }
        self.assertEqual(list(validator.iter_errors(raster)), [])


if __name__ == "__main__":
    unittest.main()
