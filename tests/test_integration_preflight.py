from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import run_integration_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]


class IntegrationPreflightTests(unittest.TestCase):
    def test_profiles_are_explicit_and_provider_inputs_are_not_implicit(self) -> None:
        self.assertEqual(preflight.parse_args(["fast"]).profile, "fast")
        self.assertEqual(
            preflight.parse_args(["ready", "--expected-head", "a" * 40]).profile,
            "ready",
        )
        self.assertEqual(
            preflight.parse_args(["providers", "--expected-head", "a" * 40]).profile,
            "providers",
        )


    def test_ready_requires_clean_tree_before_fixture_work(self) -> None:
        with patch.object(preflight, "git_output", return_value=" M changed.py"), patch.object(
            preflight, "validate_publication_lock"
        ) as lock:
            with self.assertRaisesRegex(preflight.PreflightFailure, "clean index"):
                preflight.run_ready("a" * 40)
        lock.assert_not_called()


    def test_provider_profile_rejects_non_sha_revision_without_mutating_inputs(self) -> None:
        with self.subTest("explicit roots"):
            with __import__("tempfile").TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                args = preflight.parse_args(
                    [
                        "providers",
                        "--expected-head", "a" * 40,
                        "--composition-root", str(tmp_path),
                        "--composition-revision", "composition",
                        "--policy-root", str(tmp_path),
                        "--policy-revision", "b" * 40,
                    ]
                )
                with patch.object(preflight, "require_clean_tree"), patch.object(
                    preflight, "validate_publication_lock"
                ), patch.object(preflight, "validate_producer_identity"):
                    with self.assertRaisesRegex(preflight.PreflightFailure, "full lowercase commit SHA"):
                        preflight.run_providers(args, "a" * 40)

    def test_provider_materialization_uses_isolated_checkouts(self) -> None:
        source = (ROOT / "scripts/run_integration_preflight.py").read_text(encoding="utf-8")
        self.assertIn("clone_provider_for_materialization", source)
        self.assertIn('git", "clone", "--quiet", "--shared"', source)
        self.assertIn("materialized-provider-inputs", source)
        self.assertIn("must be clean before materialization", source)


    def test_discovery_fails_if_a_test_import_is_not_represented(self) -> None:
        self.assertGreaterEqual(preflight.validate_discovery(), 43)
