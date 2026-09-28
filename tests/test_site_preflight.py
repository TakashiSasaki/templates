"""Local staged qualification must reach the exact Site consumer boundary."""
from pathlib import Path
from unittest.mock import patch
import builtins
import importlib
import io
import os
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
import unittest

from scripts import run_site_preflight as preflight
from scripts.site_check_registry import (
    ARTIFACT_LOCAL_CHECKS,
    CHECK_NAMES,
    MANAGED_VALIDATION_CHECKS,
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

    def test_jobs_must_be_at_least_one(self):
        self.assertEqual(preflight.parse_args(["fast", "--jobs", "1"]).jobs, 1)
        for value in ("0", "-1", "many"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                preflight.parse_args(["fast", "--jobs", value])

    def test_explicit_core_check_retains_assigned_site_budget(self):
        output = io.StringIO()
        with patch.object(preflight, "_git_output", return_value="a" * 40), patch.object(
            preflight, "run_check"
        ) as run_check, patch("sys.stdout", output):
            self.assertEqual(
                preflight.main(
                    ["composition-validation", "--check", "core", "--jobs", "4"]
                ),
                0,
            )
        self.assertEqual(run_check.call_args.args[1].jobs, 4)
        self.assertIn("requested=4 effective=4 runner=site-preflight", output.getvalue())

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
        reached_l0 = threading.Event()
        independent_checks = threading.Barrier(2)
        started = []
        allocations = {}

        def run_check(check, args):
            if check == "l0":
                reached_l0.set()
                return
            self.assertTrue(reached_l0.is_set())
            started.append(check)
            allocations[check] = args.jobs
            if check in {"core", "node"}:
                independent_checks.wait(timeout=5)

        with patch.object(preflight, "run_check", side_effect=run_check), patch.object(
            preflight.subprocess,
            "check_output",
            side_effect=["a" * 40, ""],
        ):
            self.assertEqual(
                preflight.main(["source-ready", "--expected-head", "a" * 40, "--jobs", "3"]),
                0,
            )
        self.assertCountEqual(started, list(SOURCE_READY_CHECKS[1:]))
        self.assertEqual(allocations["core"], 1)
        self.assertEqual(allocations["node"], 1)

    def test_jobs_one_keeps_source_ready_checks_serial_in_order(self):
        active = 0
        peak = 0
        seen = []
        lock = threading.Lock()

        def run_check(check, _args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                seen.append(check)
                active -= 1

        with patch.object(preflight, "run_check", side_effect=run_check), patch.object(
            preflight, "_git_output", side_effect=["a" * 40, ""]
        ):
            self.assertEqual(
                preflight.main(["source-ready", "--expected-head", "a" * 40, "--jobs", "1"]),
                0,
            )
        self.assertEqual(seen, list(SOURCE_READY_CHECKS))
        self.assertEqual(peak, 1)

    def test_source_ready_wave_plan_respects_assigned_budget(self):
        expected_first_waves = {
            1: [[("core", 1)], [("node", 1)]],
            2: [[("core", 1), ("node", 1)], [("site-contracts", 1), ("dependency-boundary", 1)]],
            3: [[("core", 1), ("node", 1), ("site-contracts", 1)], [("dependency-boundary", 1)]],
            4: [[("core", 1), ("node", 2), ("site-contracts", 1)], [("dependency-boundary", 1)]],
        }
        for jobs in (1, 2, 3, 4, 8):
            with self.subTest(jobs=jobs):
                waves = preflight.plan_source_ready_waves(jobs)
                self.assertTrue(all(sum(count for _, count in wave) <= jobs for wave in waves))
                self.assertEqual(
                    [check for wave in waves for check, _ in wave],
                    ["core", "node", "site-contracts", "dependency-boundary"],
                )
                if jobs in expected_first_waves:
                    self.assertEqual(waves[:2], expected_first_waves[jobs])

    def test_source_ready_python_and_node_domains_share_site_budget(self):
        expected = {
            1: [[("core", 1)], [("node", 1)], [("site-contracts", 1)], [("dependency-boundary", 1)]],
            2: [[("core", 1), ("node", 1)], [("site-contracts", 1), ("dependency-boundary", 1)]],
            3: [[("core", 1), ("node", 1), ("site-contracts", 1)], [("dependency-boundary", 1)]],
            4: [[("core", 1), ("node", 2), ("site-contracts", 1)], [("dependency-boundary", 1)]],
        }
        for jobs, expected_waves in expected.items():
            with self.subTest(jobs=jobs):
                waves = preflight.plan_source_ready_waves(jobs, core_workers=1)
                self.assertEqual(waves, expected_waves)
                self.assertTrue(all(sum(count for _, count in wave) <= jobs for wave in waves))

    def test_source_ready_child_failure_waits_for_and_reaps_wave_siblings(self):
        barrier = threading.Barrier(2)
        completed = set()

        def run_check(check, _args):
            if check == "l0":
                return
            if check in {"core", "node"}:
                barrier.wait(timeout=5)
            if check == "core":
                raise RuntimeError("controlled core failure")
            if check in {"node", "site-contracts"}:
                completed.add(check)

        with patch.object(preflight, "run_check", side_effect=run_check), patch.object(
            preflight, "_git_output", side_effect=["a" * 40, ""]
        ), patch("sys.stderr", new_callable=__import__("io").StringIO):
            with self.assertRaises(SystemExit) as raised:
                preflight.main(["source-ready", "--expected-head", "a" * 40, "--jobs", "3"])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(completed, {"node", "site-contracts"})

    def test_source_ready_does_not_start_managed_runtime_from_empty_cache(self):
        with TemporaryDirectory() as cache:
            with patch.dict(
                os.environ,
                {
                    "COMPOSITION_VALIDATION_CACHE": cache,
                    "PIP_INDEX_URL": "http://127.0.0.1:9/simple",
                    "PIP_NO_INDEX": "1",
                },
            ), patch.object(
                preflight, "_git_output", side_effect=["a" * 40, ""]
            ), patch.object(preflight, "run_l0"), patch.object(
                preflight, "run_core"
            ), patch.object(preflight, "run_node"), patch.object(
                preflight, "run_site_contracts"
            ), patch.object(preflight, "run_dependency_boundary"), patch.object(
                preflight,
                "run_composition_consumer",
                side_effect=AssertionError("source-ready attempted managed validation"),
            ):
                self.assertEqual(
                    preflight.main(["source-ready", "--expected-head", "a" * 40]),
                    0,
                )
            self.assertEqual(tuple(Path(cache).iterdir()), ())

    def test_managed_composition_validation_is_explicitly_classified(self):
        self.assertEqual(
            preflight.PROFILES["composition-validation"],
            MANAGED_VALIDATION_CHECKS,
        )
        self.assertNotIn("composition-consumer", SOURCE_READY_CHECKS)
        self.assertEqual(
            CHECK_SPECS["composition-consumer"].execution_class,
            "managed-validation",
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

    def test_l0_parses_changed_yaml_and_toml_without_running_workflow_semantics(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            yaml_path = root / "valid.yml"
            toml_path = root / "valid.toml"
            yaml_path.write_text("jobs:\n  build:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
            toml_path.write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
            with patch.object(preflight, "_changed_paths", return_value=()):
                preflight._validate_yaml(yaml_path)
                preflight._validate_toml(toml_path)

    def test_l0_rejects_invalid_yaml_and_toml(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            yaml_path = root / "invalid.yml"
            toml_path = root / "invalid.toml"
            yaml_path.write_text("jobs:\n  - broken: [\n", encoding="utf-8")
            toml_path.write_text("[project\nname = 'fixture'\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "invalid YAML syntax"):
                preflight._validate_yaml(yaml_path)
            with self.assertRaisesRegex(RuntimeError, "invalid TOML syntax"):
                preflight._validate_toml(toml_path)

    def test_node_inventory_discovers_new_matching_file_from_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            discovered = root / "tests" / "composition-playground-new.test.mjs"
            discovered.write_text("// fixture\n", encoding="utf-8")
            self.assertEqual(
                ("tests/composition-playground-new.test.mjs",),
                playground_node_tests(root),
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

    def test_node_runner_rejects_zero_worker_allocation(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            preflight.run_node(0)

    def test_node_runner_preserves_unrelated_options_and_pins_worker_budget(self):
        with patch.dict(
            os.environ,
            {
                "NODE_OPTIONS": (
                    "--max-old-space-size=2048 --test-concurrency=auto "
                    "--trace-warnings --test-concurrency 6"
                )
            },
        ), patch.object(preflight, "_run") as run:
            preflight.run_node(1)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["node", "--test", "--test-concurrency=1"])
        self.assertEqual(command[3:], list(preflight.NODE_TESTS))
        child_environment = run.call_args.kwargs["env"]
        self.assertEqual(
            child_environment["NODE_OPTIONS"],
            "--max-old-space-size=2048 --trace-warnings",
        )

    def test_core_runner_sanitizes_environment_before_python_tests_spawn_node(self):
        output = io.StringIO()
        injected = {
            "NODE_OPTIONS": "--test-concurrency=auto",
            "PYTHONPATH": "/untrusted/python-path",
            "PYTHONHOME": "/untrusted/python-home",
        }
        with patch.dict(os.environ, injected), patch.object(
            preflight, "_run"
        ) as run, patch("sys.stdout", output):
            preflight.run_core(3)
        self.assertEqual(run.call_args.args[0][-2:], ["--jobs", "3"])
        child_environment = run.call_args.kwargs["env"]
        for name in injected:
            self.assertNotIn(name, child_environment)
            self.assertIn(f"variable={name}", output.getvalue())

    def test_node_worker_count_is_capped_to_discovered_files(self):
        with patch.object(preflight, "NODE_TESTS", ("tests/one.test.mjs", "tests/two.test.mjs")), patch.object(
            preflight, "_run"
        ) as run:
            preflight.run_node(8)
        self.assertIn("--test-concurrency=2", run.call_args.args[0])

    def test_run_check_passes_site_allocation_to_node(self):
        args = preflight.parse_args(["source-ready", "--jobs", "2"])
        with patch.object(preflight, "run_node") as run_node:
            preflight.run_check("node", args)
        run_node.assert_called_once_with(2)

    def test_registry_is_the_single_playground_node_inventory(self):
        self.assertEqual(preflight.NODE_TESTS, playground_node_tests(ROOT))
        self.assertGreaterEqual(len(preflight.NODE_TESTS), 11)
        self.assertIn("tests/composition-playground-explain.test.mjs", preflight.NODE_TESTS)
        self.assertIn("tests/composition-playground-topology.test.mjs", preflight.NODE_TESTS)

    def test_local_profiles_exclude_remote_acceptance_classes(self):
        local_checks = (
            set(SOURCE_READY_CHECKS)
            | set(MANAGED_VALIDATION_CHECKS)
            | set(ARTIFACT_LOCAL_CHECKS)
        )
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
