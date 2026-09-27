from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
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

    def test_profiles_are_explicit_and_full_requires_integration_protocol(self) -> None:
        self.assertEqual(preflight.parse_args(["fast"]).profile, "fast")
        self.assertEqual(preflight.parse_args(["ready"]).profile, "ready")
        self.assertEqual(preflight.parse_args(["full"]).profile, "full")
        with self.assertRaises(SystemExit):
            preflight.parse_args(["other"])

    def test_jobs_must_be_positive_and_core_sharding_is_capped_at_two(self) -> None:
        self.assertEqual(preflight.parse_args(["fast", "--jobs", "1"]).jobs, 1)
        self.assertEqual(preflight.parse_args(["fast", "--jobs", "4"]).jobs, 4)
        for value in ("0", "-1", "many"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                preflight.parse_args(["fast", "--jobs", value])
        self.assertEqual(preflight.effective_core_jobs(4), 2)

    def test_serial_core_invocation_uses_one_shard(self) -> None:
        with mock.patch.object(preflight, "run_check") as run_check:
            preflight.run_core_test_shards(1)

        argv = run_check.call_args.args[1]
        self.assertEqual(argv[argv.index("--shard-count") + 1], "1")
        self.assertEqual(argv[argv.index("--shard-index") + 1], "0")

    def test_isolated_workspace_rejects_symlinks_that_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            external = root / "outside.txt"
            external.write_text("shared", encoding="utf-8")
            (workspace / "escape.txt").symlink_to(external)

            with self.assertRaisesRegex(
                preflight.PreflightFailure,
                "external symlink",
            ):
                preflight.validate_shard_workspace_symlinks(workspace)

    def test_parallel_core_shards_use_a_barrier_and_exact_inventory(self) -> None:
        from run_unittest_shard import digest_test_ids, shard_tests

        class ShardFixture(unittest.TestCase):
            def test_alpha(self) -> None:
                pass

            def test_beta(self) -> None:
                pass

            def test_gamma(self) -> None:
                pass

            def test_delta(self) -> None:
                pass

        selected = [
            ShardFixture("test_alpha"),
            ShardFixture("test_beta"),
            ShardFixture("test_gamma"),
            ShardFixture("test_delta"),
        ]
        inventory_digest = digest_test_ids([test.id() for test in selected])
        shards = shard_tests(selected, 2)
        barrier = threading.Barrier(2)
        outputs: list[int] = []

        def run_shard(_worktree, shard_index, _shard_count):
            barrier.wait(timeout=10)
            outputs.append(shard_index)
            shard_ids = [test.id() for test in shards[shard_index]]
            return (
                0,
                "COMPOSITION_UNITTEST_INVENTORY "
                f"suite=core discovered=4 selected=4 selected_ids_sha256={inventory_digest}\n"
                "COMPOSITION_UNITTEST_SHARD_RESULT "
                f"suite=core shard={shard_index}/2 run_count={len(shard_ids)} "
                f"run_ids_sha256={digest_test_ids(shard_ids)}\n",
                "",
                0.01,
            )

        with (
            mock.patch.object(preflight, "discover_tests", return_value=selected, create=True),
            mock.patch.object(preflight, "select_tests_for_suite", return_value=selected, create=True),
            mock.patch.object(preflight, "validate_two_shard_timing_overrides"),
            mock.patch.object(preflight, "shard_tests", side_effect=shard_tests, create=True),
            mock.patch.object(preflight, "digest_test_ids", side_effect=digest_test_ids),
            mock.patch.object(
                preflight,
                "add_shard_worktrees",
                return_value=[Path("/tmp/shard-0"), Path("/tmp/shard-1")],
            ),
            mock.patch.object(preflight, "remove_shard_worktrees") as remove,
            mock.patch.object(preflight, "run_one_core_shard", side_effect=run_shard),
        ):
            preflight.run_core_test_shards(2)

        self.assertCountEqual(outputs, [0, 1])
        remove.assert_called_once()

    def test_parallel_core_shard_failure_fails_parent_and_cleans_worktrees(self) -> None:
        from run_unittest_shard import digest_test_ids, shard_tests

        class ShardFixture(unittest.TestCase):
            def test_alpha(self) -> None:
                pass

            def test_beta(self) -> None:
                pass

        selected = [ShardFixture("test_alpha"), ShardFixture("test_beta")]
        inventory_digest = digest_test_ids([test.id() for test in selected])
        shards = shard_tests(selected, 2)
        outcomes = iter([1, 0])
        child_done: list[int] = []

        def run_shard(_worktree, shard_index, _shard_count):
            child_done.append(shard_index)
            shard_ids = [test.id() for test in shards[shard_index]]
            return (
                next(outcomes),
                "COMPOSITION_UNITTEST_INVENTORY "
                f"suite=core discovered=2 selected=2 selected_ids_sha256={inventory_digest}\n"
                "COMPOSITION_UNITTEST_SHARD_RESULT "
                f"suite=core shard={shard_index}/2 run_count={len(shard_ids)} "
                f"run_ids_sha256={digest_test_ids(shard_ids)}\n",
                "",
                0.01,
            )

        with (
            mock.patch.object(preflight, "discover_tests", return_value=selected, create=True),
            mock.patch.object(preflight, "select_tests_for_suite", return_value=selected, create=True),
            mock.patch.object(preflight, "validate_two_shard_timing_overrides"),
            mock.patch.object(preflight, "shard_tests", side_effect=shard_tests, create=True),
            mock.patch.object(preflight, "digest_test_ids", side_effect=digest_test_ids),
            mock.patch.object(
                preflight,
                "add_shard_worktrees",
                return_value=[Path("/tmp/shard-0"), Path("/tmp/shard-1")],
            ),
            mock.patch.object(preflight, "remove_shard_worktrees") as remove,
            mock.patch.object(preflight, "run_one_core_shard", side_effect=run_shard),
        ):
            with self.assertRaisesRegex(preflight.PreflightFailure, "shards failed"):
                preflight.run_core_test_shards(2)

        self.assertCountEqual(child_done, [0, 1])
        remove.assert_called_once()

    def test_owned_validator_stage_has_one_canonical_command_per_contract(self) -> None:
        recorded: list[tuple[str, tuple[str, ...]]] = []

        def record(name: str, argv, **_kwargs) -> None:
            recorded.append((name, tuple(argv)))

        with mock.patch.object(preflight, "run_check", side_effect=record):
            preflight.run_owned_validators(
                "base-sha",
                shard_count=1,
                include_integration_publication=True,
            )

        self.assertEqual(
            [name for name, _ in recorded],
            [
                "playground-generated-state",
                "composition-publication",
                "translation-availability",
                "component-version-monotonicity",
                "installer-release",
                "core-test-partition",
            ],
        )
        commands = "\n".join(" ".join(argv) for _, argv in recorded)
        self.assertEqual(commands.count("validate_translations.py"), 1)
        self.assertEqual(commands.count("validate_component_versions.py"), 1)
        self.assertIn("--base base-sha", commands)
        self.assertIn("--shard-count 1", commands)

    def test_validated_publication_artifact_skips_only_publication_checks(self) -> None:
        recorded: list[tuple[str, tuple[str, ...]]] = []

        def record(name: str, argv, **_kwargs) -> None:
            recorded.append((name, tuple(argv)))

        with mock.patch.object(preflight, "run_check", side_effect=record):
            preflight.run_owned_validators(
                "base-sha",
                shard_count=2,
                publication_already_validated=True,
            )

        self.assertEqual(
            [name for name, _ in recorded],
            [
                "translation-availability",
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

    def test_ready_keeps_composition_playground_check_without_integration_protocol(self) -> None:
        recorded: list[tuple[str, tuple[str, ...]]] = []

        def record(name: str, argv, **_kwargs) -> None:
            recorded.append((name, tuple(argv)))

        with mock.patch.object(preflight, "run_check", side_effect=record):
            preflight.run_owned_validators("base-sha")

        names = [name for name, _ in recorded]
        self.assertIn("playground-generated-state", names)
        self.assertNotIn("composition-publication", names)

    def test_ready_cleanup_removes_validation_only_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = root / "generated" / "publication-descriptor.json"
            descriptor.parent.mkdir()
            descriptor.write_text("generated", encoding="utf-8")
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "preflight.cpython.pyc").write_bytes(b"generated")

            with mock.patch.object(preflight, "PUBLICATION_DESCRIPTOR", descriptor), mock.patch.object(
                preflight, "BYTECODE_ROOTS", (root / "scripts",)
            ):
                preflight.cleanup_ready_outputs()

            self.assertFalse(descriptor.exists())
            self.assertFalse(cache.exists())

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
        ), mock.patch.object(preflight, "run_check", side_effect=record), mock.patch.object(
            preflight, "run_core_test_shards"
        ), mock.patch(
            "subprocess.run"
        ) as direct_run:
            preflight.run_full_tests(2)

        direct_run.assert_not_called()
        browser_env = dict(recorded)["real-browser-tests"]
        self.assertIsNotNone(browser_env)
        self.assertEqual(browser_env["CHROMEWEBDRIVER"], sys.executable)

    def test_full_resolves_runner_chromedriver_when_environment_is_unset(self) -> None:
        with tempfile.NamedTemporaryFile() as driver, mock.patch.dict(
            preflight.os.environ, {}, clear=True
        ), mock.patch.object(preflight.shutil, "which", return_value=driver.name):
            self.assertEqual(preflight.resolve_chromedriver(), driver.name)

    def test_full_requires_runner_chromedriver(self) -> None:
        with mock.patch.dict(preflight.os.environ, {}, clear=True), mock.patch.object(
            preflight.shutil, "which", return_value=None
        ):
            with self.assertRaisesRegex(preflight.PreflightFailure, "runner-provided"):
                preflight.resolve_chromedriver()

    def test_full_runs_distinct_consumer_spine_without_focused_suite_duplication(self) -> None:
        args = Namespace(
            profile="full",
            jobs=2,
            expected_head=None,
            publication_already_validated=False,
            validators_only=False,
            component_version_base="base-sha",
            integration_publication_protocol=ROOT,
        )
        with (
            mock.patch.object(preflight, "parse_args", return_value=args),
            mock.patch.object(preflight, "git_output", return_value="head-sha"),
            mock.patch.object(preflight, "run_check"),
            mock.patch.object(preflight, "run_owned_validators"),
            mock.patch.object(preflight, "run_consumer_spine") as consumer_spine,
            mock.patch.object(preflight, "run_focused_tests") as focused_tests,
            mock.patch.object(preflight, "run_full_tests") as full_tests,
            mock.patch.object(preflight, "run_integration_publication_contract"),
            mock.patch.dict(
                preflight.os.environ,
                {"CHROMEWEBDRIVER": sys.executable},
                clear=True,
            ),
        ):
            self.assertEqual(preflight.main([]), 0)

        consumer_spine.assert_called_once_with()
        focused_tests.assert_not_called()
        full_tests.assert_called_once_with(2)

    def test_ready_runs_cheap_checks_without_integration_or_browser(self) -> None:
        with mock.patch.object(preflight, "git_output", return_value=""), mock.patch.object(
            preflight, "run_check"
        ), mock.patch.object(preflight, "run_owned_validators") as validators, mock.patch.object(
            preflight, "run_consumer_spine"
        ) as consumer_spine, mock.patch.object(
            preflight, "run_core_ready"
        ) as core, mock.patch.object(
            preflight, "run_playground_provenance"
        ) as provenance, mock.patch.object(
            preflight, "run_dependency_boundary"
        ) as dependencies:
            preflight.run_ready("base-sha", "a" * 40, 2)

        validators.assert_called_once_with("base-sha", shard_count=2)
        consumer_spine.assert_called_once_with()
        core.assert_called_once_with(2)
        provenance.assert_called_once_with("a" * 40)
        dependencies.assert_called_once_with()

    def test_ready_rejects_dirty_tree_before_validation(self) -> None:
        with mock.patch.object(preflight, "git_output", return_value=" M changed.py"), mock.patch.object(
            preflight, "run_owned_validators"
        ) as validators:
            with self.assertRaisesRegex(preflight.PreflightFailure, "clean index"):
                preflight.run_ready("base-sha", "a" * 40, 2)
        validators.assert_not_called()

    def test_ready_requires_exact_head_argument(self) -> None:
        with mock.patch.object(preflight, "git_output", return_value="a" * 40), mock.patch.object(
            preflight, "run_ready"
        ) as ready:
            self.assertEqual(
                preflight.main(["ready", "--component-version-base", "base-sha"]),
                1,
            )
        ready.assert_not_called()


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
        self.assertLess(main.index('run_owned_validators('), main.index('run_full_tests(requested_jobs)'))

    def test_driver_build_mismatch_fails_before_launch(self):
        import composition_phase_zero as phase_zero
        with mock.patch.object(phase_zero, 'command_version', side_effect=['140.0.1.1', '139.0.1.1']):
            with self.assertRaisesRegex(RuntimeError, 'browser/driver build mismatch'):
                phase_zero.check_browser(Path(sys.executable))
