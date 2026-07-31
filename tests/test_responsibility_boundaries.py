from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402

RESPONSIBILITY_DOCUMENT = ROOT / "docs/architecture/responsibility-boundaries.md"
DEPRECATED_MAPPING = ROOT / (
    "docs/provenance/" + "agent-" + "policy-mapping.md"
)
OPTIONAL_POLICY_ARTIFACTS = {
    ".agent-policy.yml": "profiles:\n  - core\n",
    ".agent-policy.lock": '{"version": 1}\n',
}


class ResponsibilityBoundaryTests(unittest.TestCase):
    def test_responsibility_boundary_is_documented(self) -> None:
        self.assertTrue(RESPONSIBILITY_DOCUMENT.is_file())

        document = RESPONSIBILITY_DOCUMENT.read_text(encoding="utf-8")
        self.assertIn("Template-owned concerns", document)
        self.assertIn("Product-repository concerns", document)
        self.assertIn("Concerns outside the Webapp contract", document)
        self.assertIn("Independence invariant", document)
        self.assertIn(
            "A product repository may adopt such mechanisms independently.",
            document,
        )
        self.assertIn(
            "must not become prerequisites for validating or using the Webapp contracts",
            document,
        )

    def test_template_documents_keep_webapp_validation_independent(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        template = (ROOT / "TEMPLATE.md").read_text(encoding="utf-8")

        self.assertIn("coding-agent operating policy", readme)
        self.assertIn("outside the Webapp template contract", template)
        self.assertIn("may adopt such mechanisms independently", template)
        self.assertIn("not a prerequisite for using or validating this template", template)

    def test_obsolete_mapping_is_absent(self) -> None:
        self.assertFalse(DEPRECATED_MAPPING.exists())

    def test_optional_policy_artifacts_do_not_affect_contract_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
            shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
            for relative_path, content in OPTIONAL_POLICY_ARTIFACTS.items():
                (temporary_root / relative_path).write_text(content, encoding="utf-8")

            errors = validate_contracts.validate_repository(temporary_root)

        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
