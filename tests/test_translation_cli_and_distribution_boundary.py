from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_generated_repository_conformance as generated

ROOT = Path(__file__).resolve().parents[1]


class TranslationCliAndDistributionBoundaryTests(unittest.TestCase):
    def run_python(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_translation_validator_standalone_and_module_entry_points_pass(self) -> None:
        for args in (
            ("scripts/validate_translations.py",),
            ("-m", "scripts.validate_translations"),
        ):
            with self.subTest(args=args):
                result = self.run_python(*args)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("translations validated: 4", result.stdout)
                self.assertIn("guided translations: 4", result.stdout)

    def test_publication_validator_standalone_and_module_entry_points_pass(self) -> None:
        for args in (
            ("scripts/validate_publication_catalog.py",),
            ("-m", "scripts.validate_publication_catalog"),
        ):
            with self.subTest(args=args):
                result = self.run_python(*args)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("validated ", result.stdout)
                self.assertIn("publication document(s)", result.stdout)

    def test_copyable_template_excludes_translation_maintenance_artifacts(self) -> None:
        self.assertFalse((ROOT / "template" / "translations").exists())
        self.assertFalse(
            (ROOT / "template" / "scripts" / "validate_translations.py").exists()
        )
        manifest = json.loads(
            (ROOT / "distribution-manifest.json").read_text(encoding="utf-8")
        )
        forbidden = set(manifest["forbidden_distribution_paths"])
        self.assertIn("translations", forbidden)
        self.assertIn("scripts/validate_translations.py", forbidden)

    def test_clean_room_product_excludes_translation_maintenance_artifacts(self) -> None:
        with generated._generated_repository() as root:
            self.assertFalse((root / "translations").exists())
            self.assertFalse((root / "scripts" / "validate_translations.py").exists())


if __name__ == "__main__":
    unittest.main()
