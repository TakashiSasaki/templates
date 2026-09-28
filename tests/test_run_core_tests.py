from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_core_tests import (
    PROVIDER_INTEGRATION_MODULES,
    classify_test_modules,
    classify_test_inventory,
    flatten_suite,
    load_test_suite,
    outcome_digest,
    partition_test_ids,
    run_parallel_shards,
    run_suite,
    sanitize_execution_environment,
    summarize_outcomes,
    test_id_digest,
    run_tests,
)


class RunCoreTestsContractTests(unittest.TestCase):
    def test_skipped_subtest_records_parent_discovered_id(self) -> None:
        class SkippedSubtest(unittest.TestCase):
            def test_skipped_subtest(self) -> None:
                with self.subTest(case="skipped"):
                    self.skipTest("controlled subtest skip")

        case = SkippedSubtest("test_skipped_subtest")
        result = run_suite([case], verbosity=0)
        self.assertEqual(
            result.outcomes,
            {
                case.id(): {
                    "status": "skipped",
                    "reason": "controlled subtest skip",
                }
            },
        )

    def test_all_modules_classified_without_overlap(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        all_modules = sorted([f.stem for f in tests_dir.glob("test_*.py")])
        classification = classify_test_modules(tests_dir)

        core_set = set(classification["core"])
        provider_set = set(classification["provider"])

        self.assertEqual(provider_set, PROVIDER_INTEGRATION_MODULES)
        self.assertTrue(core_set.isdisjoint(provider_set))

        reconstructed = sorted(list(core_set | provider_set))
        self.assertEqual(all_modules, reconstructed)
        self.assertGreaterEqual(
            len(core_set), 100
        )  # Retained post-cutover consumer/UI module floor.
        self.assertIn("test_publication_bundle", core_set)
        self.assertIn("test_stale_translation_reader", core_set)
        self.assertIn("test_integration_boundary", core_set)

    def test_core_and_integration_preserve_discovery_case_union(self) -> None:
        def ids(suite):
            result = []
            for child in suite:
                result.extend(
                    ids(child)
                    if isinstance(child, unittest.TestSuite)
                    else [child.id()]
                )
            return result

        core = ids(load_test_suite("core"))
        integration = ids(load_test_suite("integration"))
        discovered = ids(
            unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
        )
        self.assertFalse(set(core) & set(integration))
        self.assertCountEqual(core + integration, discovered)
        self.assertFalse(PROVIDER_INTEGRATION_MODULES)
        self.assertFalse(
            any("test_exact_checked_out_provider_descriptors" in name for name in core)
        )

    def test_browser_is_not_an_empty_python_suite(self) -> None:
        with self.assertRaises(ValueError):
            load_test_suite("browser")
        workflow = (
            Path(__file__).resolve().parents[1] / ".github/workflows/build-pages.yml"
        )
        self.assertNotIn(
            "run_core_tests.py --suite browser", workflow.read_text(encoding="utf-8")
        )

    def test_missing_integration_prerequisite_is_failure(self) -> None:
        class Missing(unittest.TestCase):
            def runTest(self):
                self.skipTest("provider absent")

        with (
            patch(
                "scripts.run_core_tests.load_test_suite",
                return_value=unittest.TestSuite([Missing()]),
            ),
            patch("sys.stderr", io.StringIO()),
        ):
            self.assertEqual(run_tests("integration"), 1)

    def test_load_core_test_suite_succeeds(self) -> None:
        suite = load_test_suite("core")
        self.assertGreaterEqual(suite.countTestCases(), 735)

    def test_doc_contract_breakage_fails_core_validation(self) -> None:
        """Regression test: broken reader/documentation contract must fail core validation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            failing_test = tmp_path / "test_broken_reader_contract.py"
            failing_test.write_text(
                "import unittest\n\n"
                "class BrokenDocContractTest(unittest.TestCase):\n"
                "    def test_reader_projection_contract(self):\n"
                "        self.fail('Reader projection contract violated in lightweight path')\n",
                encoding="utf-8",
            )
            # Running tests in this temp dir must return exit code 1
            stderr_buf = io.StringIO()
            with patch("sys.stderr", stderr_buf):
                exit_code = run_tests(
                    suite_name="core", verbosity=0, tests_dir=tmp_path
                )
            self.assertEqual(1, exit_code)

    def test_test_id_shards_are_deterministic_balanced_and_complete(self) -> None:
        ids = [f"test_module.Case.test_{index}" for index in range(7)]
        serial = partition_test_ids(ids, 1)
        first = partition_test_ids(ids, 3)
        second = partition_test_ids(ids, 3)
        self.assertEqual(len(serial), 1)
        self.assertEqual(first, second)
        self.assertEqual(
            sorted(test_id for shard in first for test_id in shard), sorted(ids)
        )
        self.assertEqual(
            sum(map(len, first)),
            len(set(test_id for shard in first for test_id in shard)),
        )
        self.assertLessEqual(max(map(len, first)) - min(map(len, first)), 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            partition_test_ids([ids[0], ids[0]], 2)

    def test_new_and_changed_modules_default_to_serial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tests_dir = Path(directory) / "tests"
            tests_dir.mkdir()
            module = tests_dir / "test_reviewed.py"
            original = b"import unittest\nclass Reviewed(unittest.TestCase):\n def test_a(self): pass\n"
            module.write_bytes(original)
            ids = ["test_reviewed.Reviewed.test_a"]
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "parallel_module_sha256": {
                            "test_reviewed": {
                                "source_sha256": hashlib.sha256(original).hexdigest(),
                                "test_ids_sha256": test_id_digest(ids),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            parallel, serial = classify_test_inventory(
                ids, tests_dir=tests_dir, manifest_path=manifest_path
            )
            self.assertEqual(parallel, [ids[0]])

            expanded_ids = ids + [
                "test_reviewed.Reviewed.test_b",
                "test_new.New.test_case",
            ]
            parallel, serial = classify_test_inventory(
                expanded_ids, tests_dir=tests_dir, manifest_path=manifest_path
            )
            self.assertEqual(parallel, [])
            self.assertEqual(serial, expanded_ids)

            module.write_bytes(original + b"\n# fingerprint drift\n")
            parallel, serial = classify_test_inventory(
                expanded_ids, tests_dir=tests_dir, manifest_path=manifest_path
            )
            self.assertEqual(parallel, [])
            self.assertEqual(serial, expanded_ids)

    def test_worker_suite_imports_only_modules_assigned_to_its_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tests_dir = Path(directory) / "tests"
            tests_dir.mkdir()
            marker = Path(directory) / "unassigned-imported"
            selected_module = "test_worker_selected_fixture"
            unassigned_module = "test_worker_unassigned_fixture"
            (tests_dir / f"{selected_module}.py").write_text(
                "import unittest\n"
                "class Selected(unittest.TestCase):\n"
                "    def test_selected(self): pass\n",
                encoding="utf-8",
            )
            (tests_dir / f"{unassigned_module}.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n"
                "import unittest\n"
                "class Unassigned(unittest.TestCase):\n"
                "    def test_unassigned(self): pass\n",
                encoding="utf-8",
            )
            try:
                suite = load_test_suite(
                    "core", tests_dir, module_names={selected_module}
                )
                self.assertEqual(
                    [case.id() for case in flatten_suite(suite)],
                    [f"{selected_module}.Selected.test_selected"],
                )
                self.assertFalse(marker.exists())
            finally:
                sys.modules.pop(selected_module, None)
                sys.modules.pop(unassigned_module, None)
                sys.path.remove(str(tests_dir))

    def test_source_manifest_covers_exact_discovered_inventory(self) -> None:
        cases = flatten_suite(load_test_suite("core"))
        ids = [test.id() for test in cases]
        parallel, serial = classify_test_inventory(ids)
        self.assertFalse(set(parallel) & set(serial))
        self.assertEqual(set(parallel) | set(serial), set(ids))
        self.assertGreater(len(parallel), 0)
        self.assertGreater(len(serial), 0)

    def test_jobs_one_is_serial_and_unclassified_inventory_fails_closed(self) -> None:
        suite = unittest.TestSuite(
            [unittest.FunctionTestCase(lambda: None, description="serial fixture")]
        )
        stdout = io.StringIO()
        with (
            patch("scripts.run_core_tests.load_test_suite", return_value=suite),
            patch("sys.stdout", stdout),
            patch("scripts.run_core_tests.run_parallel_shards") as parallel,
        ):
            self.assertEqual(run_tests("core", verbosity=0, jobs=1), 0)
        parallel.assert_not_called()
        self.assertIn(
            "requested=1 effective=1 runner=site-python mode=serial-baseline",
            stdout.getvalue(),
        )

        stdout = io.StringIO()
        with (
            patch("scripts.run_core_tests.load_test_suite", return_value=suite),
            patch("sys.stdout", stdout),
            patch("scripts.run_core_tests.run_parallel_shards") as parallel,
        ):
            self.assertEqual(run_tests("core", verbosity=0, jobs=4), 0)
        parallel.assert_not_called()
        self.assertIn(
            "requested=4 effective=1 runner=site-python mode=serial-fail-closed",
            stdout.getvalue(),
        )

    def test_measured_worker_cap_keeps_parallel_and_exclusive_ids_serial(self) -> None:
        class ParallelCase(unittest.TestCase):
            def test_parallel(self):
                pass

        class ExclusiveCase(unittest.TestCase):
            def test_exclusive(self):
                pass

        parallel_case = ParallelCase("test_parallel")
        exclusive_case = ExclusiveCase("test_exclusive")
        suite = unittest.TestSuite([parallel_case, exclusive_case])
        parallel_id = parallel_case.id()
        exclusive_id = exclusive_case.id()
        original_run_suite = run_suite
        executed_ids = []

        def run_serial(cases, verbosity):
            executed_ids.extend(case.id() for case in cases)
            return original_run_suite(cases, verbosity)

        output = io.StringIO()
        with (
            patch("scripts.run_core_tests.load_test_suite", return_value=suite),
            patch(
                "scripts.run_core_tests.classify_test_inventory",
                return_value=([parallel_id], [exclusive_id]),
            ),
            patch("scripts.run_core_tests.run_parallel_shards") as run_shards,
            patch("scripts.run_core_tests.run_suite", side_effect=run_serial),
            patch("sys.stdout", output),
        ):
            self.assertEqual(run_tests("core", verbosity=0, jobs=2), 0)
        run_shards.assert_not_called()
        self.assertEqual(executed_ids, [parallel_id, exclusive_id])
        self.assertIn("requested=2 effective=1", output.getvalue())
        self.assertIn("mode=measured-serial-cap", output.getvalue())

    def test_parallel_shard_subprocesses_start_together_and_report_exact_ids(
        self,
    ) -> None:
        ids = [f"test_fixture.Case.test_{index}" for index in range(6)]
        barrier = threading.Barrier(2)
        calls = []

        def fake_subprocess(command, **kwargs):
            manifest_path = Path(command[command.index("--worker-manifest") + 1])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            barrier.wait(timeout=5)
            calls.append(manifest["shard_index"])
            outcomes = {
                test_id: {"status": "passed"} for test_id in manifest["shard_ids"]
            }
            result = {
                "shard_index": manifest["shard_index"],
                "shard_count": manifest["shard_count"],
                "ran_ids": sorted(outcomes),
                "outcomes": outcomes,
                "tests_run": len(outcomes),
                "counts": {"passed": len(outcomes)},
                "outcome_sha256": outcome_digest(outcomes),
            }
            Path(manifest["result_path"]).write_text(
                json.dumps(result), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "scripts.run_core_tests.subprocess.run", side_effect=fake_subprocess
        ):
            outcomes, failures, metrics = run_parallel_shards(
                "core", ids, ids, 2, 1, tests_dir=Path(__file__).resolve().parent
            )
        self.assertEqual(len(calls), 2)
        self.assertCountEqual(calls, (0, 1))
        self.assertEqual(set(outcomes), set(ids))
        self.assertEqual(failures, [])
        self.assertGreater(metrics["runner_wall_seconds"], 0)

    def test_parallel_child_failure_is_propagated_after_sibling_completion(
        self,
    ) -> None:
        ids = [f"test_fixture.Case.test_{index}" for index in range(4)]
        barrier = threading.Barrier(2)
        returned = []

        def fake_subprocess(command, **kwargs):
            manifest_path = Path(command[command.index("--worker-manifest") + 1])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            barrier.wait(timeout=5)
            returned.append(manifest["shard_index"])
            outcomes = {
                test_id: {"status": "passed"} for test_id in manifest["shard_ids"]
            }
            result = {
                "shard_index": manifest["shard_index"],
                "shard_count": manifest["shard_count"],
                "ran_ids": sorted(outcomes),
                "outcomes": outcomes,
                "tests_run": len(outcomes),
                "counts": {"passed": len(outcomes)},
                "outcome_sha256": outcome_digest(outcomes),
            }
            Path(manifest["result_path"]).write_text(
                json.dumps(result), encoding="utf-8"
            )
            return subprocess.CompletedProcess(
                command, int(manifest["shard_index"] == 0), "", ""
            )

        with patch(
            "scripts.run_core_tests.subprocess.run", side_effect=fake_subprocess
        ):
            outcomes, failures, _metrics = run_parallel_shards(
                "core", ids, ids, 2, 1, tests_dir=Path(__file__).resolve().parent
            )
        self.assertCountEqual(returned, (0, 1))
        self.assertEqual(set(outcomes), set(ids))
        self.assertTrue(
            any("shard 0/2 exited with 1" in failure for failure in failures)
        )

    def test_python_worker_environment_removes_path_injection(self) -> None:
        from scripts.run_core_tests import child_environment

        with patch.dict(os.environ, {"PYTHONPATH": "/untrusted/site-packages"}):
            environment = child_environment()
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)

    def test_canonical_runner_removes_ambient_node_and_python_path_options(self) -> None:
        original_path = sys.path.copy()
        output = io.StringIO()
        injected = {
            "NODE_OPTIONS": "--test-concurrency=auto",
            "PYTHONPATH": "/untrusted/site-packages",
        }
        try:
            with patch.dict(os.environ, injected), patch("sys.stdout", output):
                sanitize_execution_environment()
                for name in injected:
                    self.assertNotIn(name, os.environ)
                    self.assertIn(f"variable={name}", output.getvalue())
                self.assertNotIn("/untrusted/site-packages", sys.path)
        finally:
            sys.path[:] = original_path

    def test_subtest_errors_remain_errors_regardless_of_callback_order(self) -> None:
        class MixedSubtestOutcomes(unittest.TestCase):
            def __init__(
                self,
                method_name: str = "test_mixed_subtest_outcomes",
                *,
                reverse: bool = False,
            ):
                super().__init__(method_name)
                self.reverse = reverse

            def test_mixed_subtest_outcomes(self) -> None:
                exceptions = [AssertionError("assertion"), RuntimeError("runtime")]
                if self.reverse:
                    exceptions.reverse()
                for exception in exceptions:
                    with self.subTest(kind=type(exception).__name__):
                        raise exception

        for reverse in (False, True):
            case = MixedSubtestOutcomes(reverse=reverse)
            result = run_suite([case], verbosity=0)
            self.assertEqual(result.outcomes[case.id()]["status"], "error")
            self.assertEqual(
                summarize_outcomes(result.outcomes),
                {
                    "passed": 0,
                    "skipped": 0,
                    "failures": 0,
                    "errors": 1,
                    "expected_failures": 0,
                    "unexpected_successes": 0,
                },
            )


if __name__ == "__main__":
    unittest.main()
