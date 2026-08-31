from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "artifact.website-core"
FILES = COMPONENT / "files"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class WebsiteArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.structure = load(FILES / "contracts/site-structure.json")
        self.metadata = load(FILES / "contracts/document-metadata.json")
        self.discovery = load(FILES / "contracts/site-discovery.json")
        self.routes = load(ROOT / "components/foundation.web/files/contracts/routes.json")

    def write_fixture(self, *, evidence_mode: str = "template", structure=None, metadata=None, discovery=None, routes=None) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        docs = {
            "contracts/site-structure.json": self.structure if structure is None else structure,
            "contracts/document-metadata.json": self.metadata if metadata is None else metadata,
            "contracts/site-discovery.json": self.discovery if discovery is None else discovery,
            "contracts/routes.json": self.routes if routes is None else routes,
            "contracts/implementation-evidence.json": {"mode": evidence_mode, "commands": [], "releaseGates": [], "records": [], "requirements": []},
        }
        for relative, value in docs.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return root

    def run_contract_validator(self, root: Path):
        return subprocess.run([sys.executable, str(FILES / "scripts/validate_website_contracts.py"), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_component_and_recipe_establish_sibling_website_artifact(self) -> None:
        descriptor = load(COMPONENT / "component.json")
        recipe = load(ROOT / "recipes/website.json")
        catalog = load(ROOT / "catalog/catalog.json")
        self.assertEqual(descriptor["component_role"], "artifact")
        self.assertEqual(descriptor["requires"], ["foundation.web", "lifecycle.composition-state", "lifecycle.implementation-evidence"])
        self.assertEqual([item["id"] for item in descriptor["contract_registrations"]], ["site_structure", "document_metadata", "site_discovery"])
        self.assertEqual(recipe["artifact"], "artifact.website-core")
        self.assertEqual(recipe["optional_components"], ["capability.pwa", "capability.runtime", "capability.web-interface", "lifecycle.release-bundle"])
        self.assertIn("artifact.website-core", catalog["components"])
        self.assertIn("website", catalog["recipes"])
        self.assertNotIn("artifact.webapp-core", descriptor["requires"])

    def test_contract_schemas_and_template_seed_validate(self) -> None:
        for name in ("site-structure", "document-metadata", "site-discovery"):
            schema = load(FILES / f"schemas/{name}.schema.json")
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(load(FILES / f"contracts/{name}.json"))
        result = self.run_contract_validator(self.write_fixture())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_website_page_binds_exactly_one_shared_route(self) -> None:
        routes = copy.deepcopy(self.routes)
        routes["routes"].append({"id": "about", "path": "/about", "canonical": True, "aliases": [], "deepLink": True, "accessibility": {"documentTitleRequired": True, "focusTarget": "main-heading"}})
        result = self.run_contract_validator(self.write_fixture(routes=routes))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing page bindings", result.stderr)

        structure = copy.deepcopy(self.structure)
        structure["pages"].append({"id": "other", "routeId": "unknown", "role": "content", "title": "Other", "parentPageId": "home"})
        result = self.run_contract_validator(self.write_fixture(structure=structure))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown shared routes", result.stderr)

    def test_page_hierarchy_fails_closed_on_missing_parent_and_cycle(self) -> None:
        routes = copy.deepcopy(self.routes)
        routes["routes"].extend([
            {"id": "a", "path": "/a", "canonical": True, "aliases": [], "deepLink": True, "accessibility": {"documentTitleRequired": True, "focusTarget": "main-heading"}},
            {"id": "b", "path": "/b", "canonical": True, "aliases": [], "deepLink": True, "accessibility": {"documentTitleRequired": True, "focusTarget": "main-heading"}},
        ])
        structure = copy.deepcopy(self.structure)
        structure["pages"].extend([
            {"id": "a", "routeId": "a", "role": "content", "title": "A", "parentPageId": "b"},
            {"id": "b", "routeId": "b", "role": "content", "title": "B", "parentPageId": "a"},
        ])
        metadata = copy.deepcopy(self.metadata)
        for page_id in ("a", "b"):
            metadata["pages"].append({"pageId": page_id, "title": page_id.upper(), "description": page_id, "indexability": "index", "canonicalPathPolicy": "route-canonical", "socialPreview": "none"})
        discovery = copy.deepcopy(self.discovery)
        discovery["sitemap"]["pageIds"] = ["home", "a", "b"]
        result = self.run_contract_validator(self.write_fixture(structure=structure, metadata=metadata, discovery=discovery, routes=routes))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hierarchy contains a cycle", result.stderr)

    def test_metadata_and_sitemap_cover_the_same_page_authority(self) -> None:
        metadata = copy.deepcopy(self.metadata)
        metadata["pages"] = []
        result = self.run_contract_validator(self.write_fixture(metadata=metadata))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing document metadata", result.stderr)

        discovery = copy.deepcopy(self.discovery)
        discovery["sitemap"]["pageIds"] = []
        result = self.run_contract_validator(self.write_fixture(discovery=discovery))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly match indexable", result.stderr)

    def test_product_mode_requires_concrete_canonical_origin(self) -> None:
        result = self.run_contract_validator(self.write_fixture(evidence_mode="product"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a concrete HTTPS canonicalOrigin", result.stderr)
        discovery = copy.deepcopy(self.discovery)
        discovery["canonicalOrigin"] = "https://example.test/"
        result = self.run_contract_validator(self.write_fixture(evidence_mode="product", discovery=discovery))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_website_evidence_targets_do_not_depend_on_webapp_private_contracts(self) -> None:
        source = (FILES / "scripts/website_evidence_targets.py").read_text(encoding="utf-8")
        for forbidden in ("application_routes", "surfaces", "ui_states"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"site_structure"', source)
        self.assertIn('"document_metadata"', source)
        self.assertIn('"site_discovery"', source)
        self.assertIn('"viewports"', source)


if __name__ == "__main__":
    unittest.main()
