from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "schema-validation.yml"
VALIDATOR = ROOT / "scripts" / "validate_publication.py"
GUIDE = ROOT / "docs" / "publication-catalog.md"
PINNED_INTEGRATION_SHA = "a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d"


class PublicationProtocolConsumptionTests(unittest.TestCase):
    def test_workflow_consumes_reviewed_immutable_integration_protocol(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"ref: {PINNED_INTEGRATION_SHA}", text)
        self.assertIn("path: .integration-publication-protocol", text)
        self.assertIn("integration/publication_contract.py", text)
        self.assertIn("sparse-checkout-cone-mode: false", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("INTEGRATION_PUBLICATION_PROTOCOL_ROOT", text)
        self.assertIn("Validate Integration-owned publication contract", text)
        self.assertIn("Run canonical Composition validator preflight", text)
        self.assertIn("scripts/run_composition_preflight.py fast", text)
        self.assertNotIn("ref: site", text)
        self.assertNotIn("ref: refs/heads/site", text)
        self.assertEqual(len(PINNED_INTEGRATION_SHA), 40)
        self.assertTrue(all(character in "0123456789abcdef" for character in PINNED_INTEGRATION_SHA))

    def test_composition_validator_does_not_reimplement_generic_catalog_protocol(self):
        text = VALIDATOR.read_text(encoding="utf-8")
        for removed_implementation in (
            "def parse_catalog(",
            "def walk_asset(",
            "def paths_overlap(",
            "NAME_RE =",
            "publication catalog schema_version must be integer 3",
            "publication document IDs and sources must be unique",
            "asset destinations must not overlap",
        ):
            with self.subTest(removed_implementation=removed_implementation):
                self.assertNotIn(removed_implementation, text)
        self.assertIn("load_integration_publication_protocol", text)
        self.assertIn("load_publication_catalog", text)
        self.assertIn("validate_markdown_classification", text)
        self.assertIn("validate_reader_coverage", text)
        self.assertIn("validate_machine_coverage", text)
        self.assertIn("validate_glossary", text)

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

    def test_documentation_declares_split_authority_and_full_sha_consumption(self):
        text = GUIDE.read_text(encoding="utf-8")
        self.assertIn("Integration-owned", text)
        self.assertIn("generic schema-v3 publication protocol", text)
        self.assertIn("Composition-owned", text)
        self.assertIn("full commit SHA", text)
        self.assertIn(PINNED_INTEGRATION_SHA, text)


if __name__ == "__main__":
    unittest.main()
