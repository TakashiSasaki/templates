from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/architecture/distribution-readiness-audit.md"
BOUNDARY = ROOT / "docs/architecture/distribution-boundary.md"
CLASSIFICATION = ROOT / "docs/architecture/distribution-classification.json"
CATALOG = ROOT / "docs/publication-catalog.json"
SHARED_FIXTURE = ROOT / "tests/test_generated_repository_conformance.py"


class DistributionReadinessAuditTests(unittest.TestCase):
    def test_classification_records_the_implemented_boundary(self) -> None:
        classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))

        self.assertEqual("implemented", classification["status"])
        self.assertEqual("template", classification["targetDistributionRoot"])
        self.assertEqual(".", classification["directCopyDestination"])
        self.assertIs(classification["contentTransformationAllowed"], False)
        self.assertEqual(["template"], classification["topLevelClassification"]["distribution"])
        self.assertIn(
            "dedicated maintainer directory is not required",
            classification["maintainerLayout"],
        )
        rules = " ".join(classification["requiredSeparationRules"])
        self.assertIn("implementation", rules)
        self.assertIn("release-evidence", rules)
        self.assertIn("release-bundle", rules)

    def test_boundary_document_describes_the_implemented_layout(self) -> None:
        boundary = BOUNDARY.read_text(encoding="utf-8")

        self.assertIn("## Implemented source layout", boundary)
        self.assertIn("## Source-to-distribution projection", boundary)
        self.assertIn("**Mirrored files**", boundary)
        self.assertIn("**Distribution-owned files**", boundary)
        self.assertIn("cp -a template/.", boundary)
        self.assertIn("A separate `maintainer/` directory would not strengthen", boundary)
        self.assertNotIn("future `template/` directory", boundary)
        self.assertNotIn("The future `template/` tree", boundary)

    def test_shared_fixture_copies_the_distribution_not_the_source_root(self) -> None:
        fixture = SHARED_FIXTURE.read_text(encoding="utf-8")

        self.assertIn('DISTRIBUTION_ROOT = ROOT / "template"', fixture)
        self.assertIn("shutil.copytree(DISTRIBUTION_ROOT, root", fixture)
        self.assertNotIn("shutil.copytree(ROOT, root", fixture)
        self.assertIn('root / "distribution-manifest.json"', fixture)
        self.assertIn('root / "docs/publication-catalog.json"', fixture)
        self.assertIn('root / "scripts/validate_distribution.py"', fixture)

    def test_audit_closes_webapp_scope_without_authorizing_deployment(self) -> None:
        audit = AUDIT.read_text(encoding="utf-8")

        self.assertIn(
            "Audit status: **Webapp-internal complete; coordinated `site` integration pending.**",
            audit,
        )
        self.assertIn("This audit does not authorize GitHub Pages deployment", audit)
        self.assertIn("## Artifact identity", audit)
        self.assertIn("## Distribution closure", audit)
        self.assertIn("## Repository-root usability", audit)
        self.assertIn("## Generated-product transition", audit)
        self.assertIn("## Source and distribution CI", audit)
        self.assertIn("## Publication boundary", audit)
        self.assertIn("## Remaining repository-wide work", audit)
        self.assertIn("## Webapp release gate", audit)
        self.assertNotIn("TBD", audit)
        self.assertNotIn("TODO", audit)

    def test_publication_catalog_exposes_the_audit_as_source_material(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [
            document
            for document in catalog["documents"]
            if document["id"] == "distribution-readiness-audit"
        ]

        self.assertEqual(1, len(matches))
        self.assertEqual(
            "docs/architecture/distribution-readiness-audit.md",
            matches[0]["source"],
        )
        self.assertFalse(matches[0]["optional"])
        self.assertFalse(matches[0]["home"])
        self.assertFalse(
            (ROOT / "template/docs/architecture/distribution-readiness-audit.md").exists()
        )


if __name__ == "__main__":
    unittest.main()
