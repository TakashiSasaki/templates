from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_site_preflight as preflight
from tests.publication_context import provider_root


ROOT = Path(__file__).resolve().parents[1]


class SitePreflightTests(unittest.TestCase):
    def test_profiles_cover_owned_validation_and_exact_candidate_integration(self) -> None:
        self.assertEqual(
            ("reference-projections", "website-contract", "focused-tests"),
            preflight.PROFILES["fast"],
        )
        self.assertIn("unit-tests", preflight.PROFILES["full"])
        self.assertIn("node-explainability", preflight.PROFILES["full"])
        self.assertIn("cross-binding", preflight.PROFILES["full"])
        self.assertIn("candidate-projection", preflight.PROFILES["full"])
        self.assertEqual(
            ("cross-binding", "candidate-projection", "provider-tests", "cross-assembly"),
            preflight.PROFILES["cross"],
        )

    def test_blocking_workflows_delegate_to_named_preflight_checks(self) -> None:
        workflows = {
            "build-pages.yml": "--check unit-tests",
            "publication-materialization.yml": "--check materialization-tests",
            "publication-contract-v4.yml": "--check publication-contract-tests",
            "site-composition-playground-explain.yml": "--check node-explainability",
            "site-composition-playground-cross-authority.yml": "--check candidate-projection",
        }
        for name, expected in workflows.items():
            with self.subTest(name=name):
                text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn("run_site_preflight.py", text)
                self.assertIn(expected, text)

    def test_explicit_provider_root_is_validated_and_never_silently_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/publication-catalog.json").write_text("{}")
            with patch.dict(os.environ, {"SITE_COMPOSITION_ROOT": str(root)}):
                self.assertEqual(root.resolve(), provider_root("composition", ROOT))
            with patch.dict(os.environ, {"SITE_COMPOSITION_ROOT": ""}):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    provider_root("composition", ROOT)

    def test_exact_candidate_workflow_has_no_literal_candidate_or_continue_on_error(self) -> None:
        text = (
            ROOT
            / ".github/workflows/site-composition-playground-cross-authority.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("resolve_publication_sources.py", text)
        self.assertIn("needs.classify.outputs.composition_revision", text)
        self.assertNotIn("continue-on-error", text)


if __name__ == "__main__":
    unittest.main()
