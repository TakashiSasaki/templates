from __future__ import annotations

import sys
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTION_ROOT = SOURCE_ROOT / "template"
sys.path.insert(0, str(SOURCE_ROOT / "tests"))

import test_generated_repository_conformance as generated  # noqa: E402


class CopyableDistributionConformanceTests(unittest.TestCase):
    def test_distribution_starts_in_template_mode(self) -> None:
        self.assertEqual(DISTRIBUTION_ROOT, generated.DISTRIBUTION_ROOT)
        for relative in (
            "contracts/implementation-evidence.json",
            "contracts/release-evidence.json",
            "contracts/release-bundle.json",
        ):
            with self.subTest(relative=relative):
                document = generated._load_json(DISTRIBUTION_ROOT / relative)
                self.assertEqual("template", document["mode"])

    def test_clean_room_product_is_created_from_distribution_only(self) -> None:
        canonical_evidence = generated._load_json(
            DISTRIBUTION_ROOT / "contracts/implementation-evidence.json"
        )
        self.assertEqual("template", canonical_evidence["mode"])

        with generated._generated_repository() as root:
            self.assertFalse((root / ".git").exists())
            self.assertFalse((root / "template").exists())
            self.assertFalse((root / "distribution-manifest.json").exists())
            self.assertFalse((root / "docs/publication-catalog.json").exists())
            self.assertFalse((root / "docs/publication-catalog.md").exists())
            self.assertFalse((root / "scripts/validate_distribution.py").exists())
            self.assertFalse(
                (root / "scripts/validate_publication_catalog.py").exists()
            )
            self.assertFalse(
                (root / "tests/test_generated_repository_conformance.py").exists()
            )
            self.assertEqual(
                "product",
                generated._load_json(
                    root / "contracts/implementation-evidence.json"
                )["mode"],
            )

            proof = generated._run_generated_python(
                root,
                "product/prove_conformance.py",
            )
            self.assertEqual(0, proof.returncode, proof.stderr)
            self.assertIn("generated repository proof: 52 checks passed", proof.stdout)

            commands = (
                ("scripts/validate_contracts.py",),
                ("-m", "scripts.validate_contracts"),
                ("scripts/validate_contract_evolution.py",),
                ("-m", "scripts.validate_contract_evolution"),
                ("scripts/validate_implementation_evidence.py",),
                ("-m", "scripts.validate_implementation_evidence"),
            )
            for command in commands:
                with self.subTest(command=command):
                    result = generated._run_generated_python(root, *command)
                    self.assertEqual(
                        0,
                        result.returncode,
                        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                    )

        self.assertEqual(
            "template",
            generated._load_json(
                DISTRIBUTION_ROOT / "contracts/implementation-evidence.json"
            )["mode"],
        )
        self.assertFalse((SOURCE_ROOT / "product").exists())
        self.assertFalse((DISTRIBUTION_ROOT / "product").exists())

    def test_distribution_fixture_rejects_template_mode_residue(self) -> None:
        with generated._generated_repository() as root:
            evidence_path = root / "contracts/implementation-evidence.json"
            evidence = generated._load_json(evidence_path)
            evidence["mode"] = "template"
            generated._write_json(evidence_path, evidence)

            result = generated._run_generated_python(
                root,
                "scripts/validate_implementation_evidence.py",
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "template mode requires commands to be empty",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
