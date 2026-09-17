"""Local staged qualification must reach the exact Site consumer boundary."""
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import unittest

from scripts import run_site_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]


class SitePreflightTests(unittest.TestCase):
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
                preflight.main(["ready", "--expected-head", "wrong"])
        check_output.assert_called_once()
        run_check.assert_not_called()

    def test_ready_profile_runs_l0_core_node_and_exact_assembly(self):
        with patch.object(preflight, "run_check") as run_check, patch.object(
            preflight.subprocess, "check_output", return_value="a" * 40
        ):
            self.assertEqual(preflight.main(["ready", "--expected-head", "a" * 40]), 0)
        self.assertEqual(
            [call.args[0] for call in run_check.call_args_list],
            ["l0", "core", "node", "assembly"],
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
        with patch.object(preflight, "load_lock", return_value=lock), patch.object(
            preflight.acquire, "locate", return_value=receipt
        ) as locate, patch.object(preflight.acquire, "consume") as consume, patch.object(
            preflight, "render"
        ) as render, patch.object(preflight, "check_site_artifact", return_value={"html_pages": 1}):
            result = preflight.run_exact_assembly(None, None)
        locate.assert_called_once_with(lock)
        consume.assert_called_once()
        render.assert_called_once()
        self.assertEqual(result, {"html_pages": 1})

    def test_exact_assembly_fails_when_no_exact_bundle_is_available(self):
        with patch.object(preflight, "load_lock", return_value={"revision": "c" * 40}), patch.object(
            preflight.acquire, "locate", return_value=None
        ), self.assertRaisesRegex(RuntimeError, "no exact qualified"):
            preflight.run_exact_assembly(None, None)

    def test_assembly_failure_is_not_converted_to_success(self):
        with patch.object(preflight, "run_exact_assembly", side_effect=RuntimeError("render failed")):
            with self.assertRaises(SystemExit) as raised:
                preflight.main(["ready", "--check", "assembly"])
        self.assertEqual(raised.exception.code, 2)

    def test_empty_node_test_inventory_fails_closed(self):
        with patch.object(preflight, "NODE_TESTS", ()):
            with self.assertRaisesRegex(RuntimeError, "no Composition Playground"):
                preflight.run_node()
