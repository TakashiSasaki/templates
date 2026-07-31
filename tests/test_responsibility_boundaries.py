from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESPONSIBILITY_DOCUMENT = ROOT / "docs/architecture/responsibility-boundaries.md"
DEPRECATED_MAPPING = ROOT / (
    "docs/provenance/" + "agent-" + "policy-mapping.md"
)
POLICY_NAME = "agent-" + "policy"
POLICY_GENERATED_ARTIFACTS = (
    ROOT / (".agent-" + "policy.yml"),
    ROOT / (".agent-" + "policy.lock"),
)


class ResponsibilityBoundaryTests(unittest.TestCase):
    def test_responsibility_boundary_is_documented(self) -> None:
        self.assertTrue(RESPONSIBILITY_DOCUMENT.is_file())

        document = RESPONSIBILITY_DOCUMENT.read_text(encoding="utf-8")
        self.assertIn("Template-owned concerns", document)
        self.assertIn("Product-repository concerns", document)
        self.assertIn("Concerns outside the Webapp contract", document)
        self.assertIn("Independence invariant", document)

    def test_template_documentation_does_not_delegate_design_authority(self) -> None:
        documentation_paths = [ROOT / "README.md", ROOT / "TEMPLATE.md"]
        documentation_paths.extend(sorted((ROOT / "docs").rglob("*.md")))

        for path in documentation_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8").lower()
                self.assertNotIn(POLICY_NAME, text)

    def test_obsolete_mapping_and_policy_generated_artifacts_are_absent(self) -> None:
        self.assertFalse(DEPRECATED_MAPPING.exists())
        for path in POLICY_GENERATED_ARTIFACTS:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
