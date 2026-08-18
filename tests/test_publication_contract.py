from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_publication.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("composition_publication_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompositionPublicationContractTests(unittest.TestCase):
    def test_provider_publication_is_valid(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Composition publication validation: OK", result.stdout)

    def test_catalog_is_composition_owned_and_has_one_home(self):
        catalog = json.loads((ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 3)
        homes = [entry for entry in catalog["documents"] if entry["home"]]
        self.assertEqual(len(homes), 1)
        self.assertEqual(homes[0]["source"], "README.md")
        sources = {entry["source"] for entry in catalog["documents"]}
        self.assertIn("components/artifact.skill-core/files/SKILL.md", sources)
        self.assertIn("components/artifact.webapp-core/files/TEMPLATE.md", sources)
        self.assertIn("components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md", sources)
        self.assertNotIn("template/SKILL.md", sources)
        self.assertNotIn("template/README.md", sources)

    def test_publication_assets_cover_closed_production_authorities(self):
        validator = load_validator()
        documents, assets, glossary = validator.parse_catalog()
        validator.validate_reader_coverage(documents)
        validator.validate_machine_coverage(assets)
        self.assertEqual(glossary.as_posix(), "docs/glossary.yml")

    def test_glossary_is_strict_json_yaml_subset_and_drops_retired_copy_model(self):
        raw = (ROOT / "docs" / "glossary.yml").read_text(encoding="utf-8")
        self.assertTrue(raw.lstrip().startswith("{"))
        glossary = json.loads(raw)
        ids = {term["id"] for term in glossary["terms"]}
        self.assertIn("templates-skill-profile", ids)
        self.assertIn("templates-composition-component", ids)
        self.assertIn("templates-contract-manifest", ids)
        self.assertNotIn("templates-webapp-template-distribution-artifact", ids)
        self.assertNotIn("templates-skill-mcp-extension", ids)

    def test_guided_index_local_links_remain_inside_source_and_exist(self):
        index_path = ROOT / "docs" / "index.md"
        text = index_path.read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        self.assertTrue(links)
        for target in links:
            with self.subTest(target=target):
                self.assertFalse(target.startswith(("http://", "https://", "/")))
                path = (index_path.parent / target).resolve()
                path.relative_to(ROOT.resolve())
                self.assertTrue(path.exists(), target)
                self.assertFalse(path.is_symlink(), target)


if __name__ == "__main__":
    unittest.main()
