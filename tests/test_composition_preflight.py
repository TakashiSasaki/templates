from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_composition_preflight as preflight  # noqa: E402


class CompositionPreflightTests(unittest.TestCase):
    def test_profiles_are_explicit_and_full_requires_site_protocol(self) -> None:
        self.assertEqual(preflight.parse_args(["fast"]).profile, "fast")
        self.assertEqual(preflight.parse_args(["full"]).profile, "full")
        with self.assertRaises(SystemExit):
            preflight.parse_args(["other"])

    def test_owned_validator_stage_has_one_canonical_command_per_contract(self) -> None:
        recorded: list[tuple[str, tuple[str, ...]]] = []

        def record(name: str, argv, **_kwargs) -> None:
            recorded.append((name, tuple(argv)))

        with mock.patch.object(preflight, "run_check", side_effect=record):
            preflight.run_owned_validators("base-sha")

        self.assertEqual(
            [name for name, _ in recorded],
            [
                "playground-generated-state",
                "composition-publication",
                "translation-freshness",
                "component-version-monotonicity",
                "installer-release",
                "core-test-partition",
            ],
        )
        commands = "\n".join(" ".join(argv) for _, argv in recorded)
        self.assertEqual(commands.count("validate_translations.py"), 1)
        self.assertEqual(commands.count("validate_component_versions.py"), 1)
        self.assertIn("--base base-sha", commands)

    def test_failed_named_check_is_fail_closed(self) -> None:
        completed = subprocess.CompletedProcess(["false"], 7)
        with mock.patch("subprocess.run", return_value=completed):
            with self.assertRaisesRegex(preflight.PreflightFailure, "exit code 7"):
                preflight.run_check("example", ["false"])

    def test_full_reuses_a_preprovisioned_absolute_chromedriver(self) -> None:
        recorded: list[tuple[str, dict[str, str] | None]] = []

        def record(name: str, _argv, *, env=None) -> None:
            recorded.append((name, env))

        with mock.patch.dict(
            preflight.os.environ,
            {"CHROMEWEBDRIVER": sys.executable},
        ), mock.patch.object(preflight, "run_check", side_effect=record), mock.patch(
            "subprocess.run"
        ) as direct_run:
            preflight.run_full_tests()

        direct_run.assert_not_called()
        browser_env = dict(recorded)["real-browser-tests"]
        self.assertIsNotNone(browser_env)
        self.assertEqual(browser_env["CHROMEWEBDRIVER"], sys.executable)


if __name__ == "__main__":
    unittest.main()
