from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "components" / "foundation.web"
COMPONENT = FOUNDATION / "component.json"
GUIDANCE = FOUNDATION / "files" / "docs" / "url-path-design-guidance.md"
ROUTES_SCHEMA = FOUNDATION / "files" / "schemas" / "routes.schema.json"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"
DOCS_INDEX = ROOT / "docs" / "index.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def route_document(path: str) -> dict:
    return {
        "$schema": "../schemas/routes.schema.json",
        "schemaVersion": 4,
        "routes": [
            {
                "id": "account-settings",
                "path": path,
                "canonical": True,
                "aliases": [],
                "deepLink": True,
                "accessibility": {
                    "documentTitleRequired": True,
                    "focusTarget": "main-heading",
                },
            }
        ],
    }


def validation_errors(path: str) -> list:
    schema = load_json(ROUTES_SCHEMA)
    return list(Draft202012Validator(schema).iter_errors(route_document(path)))


class WebUrlPathGuidanceTests(unittest.TestCase):
    def test_guidance_is_managed_material_but_not_a_contract(self) -> None:
        component = load_json(COMPONENT)
        self.assertTrue(GUIDANCE.is_file())

        material = next(
            item
            for item in component["materials"]
            if item.get("source") == "files/docs/url-path-design-guidance.md"
        )
        self.assertEqual(material["destination"], "docs/url-path-design-guidance.md")
        self.assertEqual(material["ownership"], "managed")

        registrations = component["contract_registrations"]
        self.assertNotIn(
            "docs/url-path-design-guidance.md",
            {item["document"] for item in registrations},
        )
        routes = next(item for item in registrations if item["id"] == "routes")
        self.assertEqual(routes["document"], "contracts/routes.json")
        self.assertEqual(routes["schema"], "schemas/routes.schema.json")
        self.assertEqual(routes["document_schema_version"], 4)

    def test_guidance_is_reader_discoverable_without_becoming_machine_contract(self) -> None:
        catalog = load_json(PUBLICATION_CATALOG)
        by_id = {item["id"]: item for item in catalog["documents"]}
        entry = by_id["web-url-path-design-guidance"]
        self.assertEqual(
            entry["source"],
            "components/foundation.web/files/docs/url-path-design-guidance.md",
        )
        self.assertFalse(entry["optional"])
        self.assertFalse(entry["home"])

        docs_index = DOCS_INDEX.read_text(encoding="utf-8")
        self.assertIn(
            "../components/foundation.web/files/docs/url-path-design-guidance.md",
            docs_index,
        )

    def test_advisory_wording_does_not_use_normative_rfc_keywords(self) -> None:
        guidance = GUIDANCE.read_text(encoding="utf-8")
        self.assertIn("Composition-owned advisory guidance", guidance)
        self.assertIn("A route may depart from this guidance without", guidance)
        self.assertIn("This is a style preference, not a route-validity rule", guidance)
        self.assertIsNone(re.search(r"\b(?:MUST|SHOULD|MAY)\b", guidance))

    def test_guidance_deviation_remains_normatively_valid(self) -> None:
        self.assertEqual([], validation_errors("/Account_Settings.HTML"))

    def test_guidance_cannot_waive_normative_representation_rules(self) -> None:
        for path in ("relative/path", "/a/../b", "/reports/", "/café"):
            with self.subTest(path=path):
                self.assertTrue(validation_errors(path))


if __name__ == "__main__":
    unittest.main()
