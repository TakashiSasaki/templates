from __future__ import annotations

import subprocess
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_composition_preflight as preflight  # noqa: E402


class CompositionPreflightTests(unittest.TestCase):
    def test_validation_environment_prevents_source_tree_bytecode_drift(self) -> None:
        with mock.patch.dict(preflight.os.environ, {}, clear=True):
            preflight.configure_validation_environment()
            self.assertEqual(preflight.os.environ["PYTHONDONTWRITEBYTECODE"], "1")

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

    def test_validated_publication_artifact_skips_only_publication_checks(self) -> None:
        recorded: list[tuple[str, tuple[str, ...]]] = []

        def record(name: str, argv, **_kwargs) -> None:
            recorded.append((name, tuple(argv)))

        with mock.patch.object(preflight, "run_check", side_effect=record):
            preflight.run_owned_validators(
                "base-sha",
                publication_already_validated=True,
            )

        self.assertEqual(
            [name for name, _ in recorded],
            [
                "translation-freshness",
                "component-version-monotonicity",
                "installer-release",
                "core-test-partition",
            ],
        )
        commands = "\n".join(" ".join(argv) for _, argv in recorded)
        self.assertNotIn("generate_composition_playground_publication.py", commands)
        self.assertNotIn("validate_publication.py", commands)
        self.assertIn("validate_translations.py", commands)
        self.assertIn("validate_component_versions.py", commands)

    def test_publication_reuse_flag_is_explicit(self) -> None:
        args = preflight.parse_args(
            ["fast", "--validators-only", "--publication-already-validated"]
        )
        self.assertTrue(args.validators_only)
        self.assertTrue(args.publication_already_validated)

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

    def test_full_runs_distinct_consumer_spine_without_focused_suite_duplication(self) -> None:
        args = Namespace(
            profile="full",
            expected_head=None,
            publication_already_validated=False,
            validators_only=False,
            component_version_base="base-sha",
            site_publication_protocol=ROOT,
        )
        with (
            mock.patch.object(preflight, "parse_args", return_value=args),
            mock.patch.object(preflight, "git_output", return_value="head-sha"),
            mock.patch.object(preflight, "run_check"),
            mock.patch.object(preflight, "run_owned_validators"),
            mock.patch.object(preflight, "run_consumer_spine") as consumer_spine,
            mock.patch.object(preflight, "run_focused_tests") as focused_tests,
            mock.patch.object(preflight, "run_full_tests") as full_tests,
            mock.patch.object(preflight, "run_site_publication_contract"),
            mock.patch.dict(
                preflight.os.environ,
                {"CHROMEWEBDRIVER": sys.executable},
                clear=True,
            ),
        ):
            self.assertEqual(preflight.main([]), 0)

        consumer_spine.assert_called_once_with()
        focused_tests.assert_not_called()
        full_tests.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

class PhaseZeroBoundaryTests(unittest.TestCase):
    def test_existing_bytecode_is_rejected_before_source_loader(self):
        import tempfile
        import composition_phase_zero as phase_zero
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'components/example/files/__pycache__'
            cache.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, 'pre-existing generated source contamination'):
                phase_zero.check_source(root)

    def test_phase_zero_precedes_owned_validators_and_full_core(self):
        source = (SCRIPTS / 'run_composition_preflight.py').read_text()
        main = source[source.index('def main('):]
        self.assertLess(main.index('"phase-zero-browser"'), main.index('run_owned_validators('))
        self.assertLess(main.index('run_owned_validators('), main.index('run_full_tests()'))

    def test_driver_build_mismatch_fails_before_launch(self):
        import composition_phase_zero as phase_zero
        import prepare_chromedriver
        with mock.patch.object(prepare_chromedriver, 'command_version', side_effect=['140.0.1.1', '139.0.1.1']):
            with self.assertRaisesRegex(RuntimeError, 'browser/driver build mismatch'):
                phase_zero.check_browser(Path(sys.executable))
