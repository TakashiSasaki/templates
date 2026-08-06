from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplateBaselineTests(unittest.TestCase):
    def test_distribution_has_the_required_repository_root(self) -> None:
        required = {
            ".github/workflows/contract-validation.yml",
            ".gitignore",
            "README.md",
            "TEMPLATE.md",
            "contracts/manifest.json",
            "contracts/implementation-evidence.json",
            "contracts/release-evidence.json",
            "contracts/release-bundle.json",
            "schemas/contract-manifest.schema.json",
            "scripts/validate_contracts.py",
            "scripts/validate_contract_evolution.py",
            "scripts/validate_implementation_evidence.py",
            "scripts/validate_release_evidence.py",
            "scripts/validate_release_bundle.py",
            "requirements-dev.lock",
        }
        missing = sorted(path for path in required if not (ROOT / path).is_file())
        self.assertEqual([], missing)

    def test_initial_evidence_documents_are_explicitly_template_mode(self) -> None:
        for relative in (
            "contracts/implementation-evidence.json",
            "contracts/release-evidence.json",
            "contracts/release-bundle.json",
        ):
            with self.subTest(relative=relative):
                document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                self.assertEqual("template", document["mode"])

    def test_source_maintainer_artifacts_are_absent(self) -> None:
        forbidden = {
            "docs/publication-catalog.json",
            "docs/publication-catalog.md",
            "docs/architecture/completion-roadmap.md",
            "docs/architecture/distribution-boundary.md",
            "docs/architecture/distribution-classification.json",
            "docs/architecture/final-readiness-audit.md",
            "docs/architecture/generated-repository-conformance.md",
            "scripts/validate_publication_catalog.py",
        }
        present = sorted(path for path in forbidden if (ROOT / path).exists())
        self.assertEqual([], present)

    def test_all_retained_validator_entry_points_pass_from_distribution_root(self) -> None:
        commands = (
            ("scripts/validate_contracts.py",),
            ("-m", "scripts.validate_contracts"),
            ("scripts/validate_contract_evolution.py",),
            ("-m", "scripts.validate_contract_evolution"),
            ("scripts/validate_implementation_evidence.py",),
            ("-m", "scripts.validate_implementation_evidence"),
            ("scripts/validate_release_evidence.py",),
            ("-m", "scripts.validate_release_evidence"),
            ("scripts/validate_release_bundle.py",),
            ("-m", "scripts.validate_release_bundle"),
        )
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
