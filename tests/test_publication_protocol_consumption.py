from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "schema-validation.yml"
VALIDATOR = ROOT / "scripts" / "validate_publication.py"
GUIDE = ROOT / "docs" / "publication-catalog.md"

class PublicationProtocolConsumptionTests(unittest.TestCase):
    def test_publication_validation_uses_local_parser(self):
        self.assertIn('scripts/publication_catalog.py', WORKFLOW.read_text())
        self.assertIn('import publication_catalog', VALIDATOR.read_text())
        self.assertNotIn('.integration-publication-protocol', WORKFLOW.read_text())


    def test_site_publication_dependency_stays_out_of_consumer_runtime(self):
        runtime_paths = [ROOT / "scripts" / "compose.py"]
        runtime_paths.extend(sorted((ROOT / "scripts").glob("composer_*.py")))
        runtime_paths.extend(
            [
                ROOT
                / "components"
                / "lifecycle.composition-state"
                / "files"
                / ".template-composition"
                / "validate_composition.py",
                ROOT / "recipes" / "skill.json",
                ROOT / "recipes" / "webapp.json",
            ]
        )
        self.assertGreaterEqual(len(runtime_paths), 11)

        forbidden_dependencies = (
            "publication_contract",
            "INTEGRATION_PUBLICATION_PROTOCOL_ROOT",
            "load_integration_publication_protocol",
            ".integration-publication-protocol",
        )
        for path in runtime_paths:
            text = path.read_text(encoding="utf-8")
            for dependency in forbidden_dependencies:
                with self.subTest(
                    path=path.relative_to(ROOT).as_posix(),
                    dependency=dependency,
                ):
                    self.assertNotIn(dependency, text)


if __name__ == "__main__":
    unittest.main()
