"""Local staged qualification must reach the exact Site consumer boundary."""
from pathlib import Path
from unittest.mock import patch
import builtins
import importlib
import subprocess
import sys
import unittest

from scripts import run_site_preflight as preflight
from scripts.site_check_registry import (
    ARTIFACT_LOCAL_CHECKS,
    CHECK_NAMES,
    REMOTE_CHECKS,
    REMOTE_ACCEPTANCE_CLASSES,
    SOURCE_READY_CHECKS,
    CHECK_SPECS,
    playground_node_tests,
)


ROOT = Path(__file__).resolve().parents[1]


class SitePreflightTests(unittest.TestCase):
    def test_node_preflight_imports_without_build_only_dependencies(self):
        original_import = builtins.__import__

        def reject_build_dependency(name, *args, **kwargs):
            if name == "idna":
                raise ImportError("blocked for L0 dependency test")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", reject_build_dependency):
            importlib.reload(preflight)

    def test_provider_checkout_arguments_are_rejected(self):
        for argument in ("--composition-root", "--policy-root", "--staging-id"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/run_site_preflight.py"), "fast", argument, "x"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments", result.stderr)

    def test_exact_head_guard_precedes_validation(self):
        with patch.object(
            preflight.subprocess,
            "check_output",
            return_value="a" * 40,
        ) as check_output, patch.object(preflight, "run_check") as run_check:
            with self.assertRaises(SystemExit):
                preflight.main(["source-ready", "--expected-head", "wrong"])
        check_output.assert_called_once()
        run_check.assert_not_called()

    def test_source_ready_profile_runs_every_cheap_source_check(self):
        with patch.object(preflight, "run_check") as run_check, patch.object(
            preflight.subprocess,
            "check_output",
            side_effect=["a" * 40, ""],
        ):
            self.assertEqual(preflight.main(["source-ready", "--expected-head", "a" * 40]), 0)
        self.assertEqual(
            [call.args[0] for call in run_check.call_args_list],
            list(SOURCE_READY_CHECKS),
        )

    def test_source_ready_requires_an_explicit_expected_head(self):
        with patch.object(preflight, "run_check") as run_check, patch.object(
            preflight.subprocess, "check_output", return_value="a" * 40
        ):
            with self.assertRaises(SystemExit):
                preflight.main(["source-ready"])
        run_check.assert_not_called()

    def test_source_ready_rejects_staged_unstaged_and_untracked_changes(self):
        for status in ("M  staged.py", " M unstaged.py", "?? untracked.py"):
            with self.subTest(status=status):
                with patch.object(
                    preflight.subprocess,
                    "check_output",
                    side_effect=["a" * 40, status],
                ), patch.object(preflight, "run_check") as run_check:
                    with self.assertRaises(SystemExit):
                        preflight.main(["source-ready", "--expected-head", "a" * 40])
                run_check.assert_not_called()

    def test_fast_changed_paths_include_committed_staged_unstaged_and_untracked(self):
        with patch.object(
            preflight.subprocess,
            "check_output",
            side_effect=[
                "committed.py\nshared.py\n",
                "staged.py\nshared.py\n",
                "unstaged.py\nshared.py\n",
                "untracked.py\nshared.py\n",
            ],
        ):
            paths = preflight._changed_paths("base", None)
        self.assertEqual(
            paths,
            ("committed.py", "shared.py", "staged.py", "unstaged.py", "untracked.py"),
        )

    def test_l0_runs_changed_python_test_modules(self):
        with patch.object(preflight, "_run") as run, patch.object(
            preflight, "_changed_paths", return_value=("tests/test_github_urls.py",)
        ), patch.object(preflight, "classify_paths"):
            preflight.run_l0("HEAD^", None)
        self.assertIn(
            [sys.executable, "-m", "unittest", "tests.test_github_urls"],
            [call.args[0] for call in run.call_args_list],
        )

    def test_exact_assembly_uses_located_bundle_and_actual_renderer(self):
        lock = {"bundle_identity": "b" * 64}
        receipt = {"artifact_id": 9}
        with patch("site_renderer.bundle.load_lock", return_value=lock), patch(
            "site_renderer.acquire.locate", return_value=receipt
        ) as locate, patch("site_renderer.acquire.consume") as consume, patch(
            "site_renderer.render.render"
        ) as render, patch("scripts.check_site_artifact.check", return_value={"html_pages": 1}):
            result = preflight.run_exact_assembly(None, None)
        locate.assert_called_once_with(lock)
        consume.assert_called_once()
        render.assert_called_once()
        self.assertEqual(result, {"html_pages": 1})

    def test_exact_assembly_fails_when_no_exact_bundle_is_available(self):
        with patch("site_renderer.bundle.load_lock", return_value={"revision": "c" * 40}), patch(
            "site_renderer.acquire.locate", return_value=None
        ), self.assertRaisesRegex(RuntimeError, "no exact qualified"):
            preflight.run_exact_assembly(None, None)

    def test_assembly_failure_is_not_converted_to_success(self):
        with patch.object(preflight, "run_exact_assembly", side_effect=RuntimeError("render failed")), patch.object(
            preflight.subprocess,
            "check_output",
            side_effect=["a" * 40, ""],
        ):
            with self.assertRaises(SystemExit) as raised:
                preflight.main(["source-ready", "--expected-head", "a" * 40, "--check", "assembly"])
        self.assertEqual(raised.exception.code, 2)

    def test_empty_node_test_inventory_fails_closed(self):
        with patch.object(preflight, "NODE_TESTS", ()):
            with self.assertRaisesRegex(RuntimeError, "no Composition Playground"):
                preflight.run_node()

    def test_registry_is_the_single_playground_node_inventory(self):
        self.assertEqual(preflight.NODE_TESTS, playground_node_tests(ROOT))
        self.assertGreaterEqual(len(preflight.NODE_TESTS), 11)
        self.assertIn("tests/composition-playground-explain.test.mjs", preflight.NODE_TESTS)
        self.assertIn("tests/composition-playground-topology.test.mjs", preflight.NODE_TESTS)

    def test_local_profiles_exclude_remote_acceptance_classes(self):
        local_checks = set(SOURCE_READY_CHECKS) | set(ARTIFACT_LOCAL_CHECKS)
        self.assertEqual(set(preflight.CHECKS), set(CHECK_NAMES))
        self.assertTrue(local_checks)
        self.assertEqual(
            {spec.execution_class for spec in REMOTE_CHECKS},
            set(REMOTE_ACCEPTANCE_CLASSES),
        )
        self.assertTrue(
            all(CHECK_SPECS[name].execution_class not in REMOTE_ACCEPTANCE_CLASSES for name in local_checks)
        )

    def test_artifact_local_profile_requires_both_artifact_inputs(self):
        with patch.object(preflight, "run_check") as run_check, patch.object(
            preflight.subprocess, "check_output", return_value="a" * 40
        ):
            with self.assertRaises(SystemExit):
                preflight.main(["artifact-local"])
        run_check.assert_not_called()

    def test_composition_consumer_uses_managed_validator(self):
        with patch.object(preflight, "_run") as run:
            preflight.run_composition_consumer()
        run.assert_called_once_with(
            [sys.executable, ".template-composition/validate.py", "."]
        )

    def test_site_contract_check_runs_existing_and_new_site_boundaries(self):
        with patch.object(preflight, "_run") as run:
            preflight.run_site_contracts()
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                [sys.executable, "scripts/validate_website_contracts.py", "."],
                [sys.executable, "scripts/validate_site_declarations.py", "."],
            ],
        )

    def test_dependency_boundary_uses_static_contract_runner(self):
        with patch.object(preflight, "_run") as run:
            preflight.run_dependency_boundary()
        run.assert_called_once_with(
            [sys.executable, "scripts/check_python_dependencies.py"]
        )
