from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
import sys
import time
from types import ModuleType
import unittest
from unittest.mock import patch

from scripts import run_integration_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]


class IntegrationPreflightTests(unittest.TestCase):
    def test_class_fixture_skip_accounts_every_discovered_id(self) -> None:
        class SkippedClass(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest("controlled class fixture skip")

            def test_one(self):
                pass

            def test_two(self):
                pass

        cases = [SkippedClass("test_one"), SkippedClass("test_two")]
        test_ids = [case.id() for case in cases]
        with (
            patch.object(preflight, "classify_test_inventory", return_value=([], test_ids)),
            redirect_stdout(io.StringIO()) as output,
        ):
            status = preflight.run_discovered_tests(cases, jobs=2, verbosity=0)

        self.assertEqual(status, 0)
        self.assertIn("tests_run=2 passed=0 skipped=2 failures=0 errors=0", output.getvalue())
        self.assertNotIn("omitted test IDs", output.getvalue())

    def test_teardown_class_skip_does_not_add_a_synthetic_test_id(self) -> None:
        class TeardownSkippedClass(unittest.TestCase):
            def test_case_passed_before_teardown(self):
                pass

            @classmethod
            def tearDownClass(cls):
                raise unittest.SkipTest("controlled teardown skip")

        case = TeardownSkippedClass("test_case_passed_before_teardown")
        result = preflight.run_suite([case], verbosity=0)
        self.assertEqual(result.outcomes, {case.id(): {"status": "passed"}})

    def test_teardown_module_skip_does_not_add_a_synthetic_test_id(self) -> None:
        module_name = "test_integration_teardown_module_skip"
        module = ModuleType(module_name)

        def tear_down_module():
            raise unittest.SkipTest("controlled module teardown skip")

        module.tearDownModule = tear_down_module
        case_type = type(
            "TeardownSkippedModule",
            (unittest.TestCase,),
            {
                "__module__": module_name,
                "test_case_passed_before_teardown": lambda self: None,
            },
        )
        sys.modules[module_name] = module
        try:
            case = case_type("test_case_passed_before_teardown")
            result = preflight.run_suite([case], verbosity=0)
        finally:
            sys.modules.pop(module_name, None)
        self.assertEqual(result.outcomes, {case.id(): {"status": "passed"}})

    def test_module_fixture_skip_preserves_worker_inventory(self) -> None:
        module_name = "test_integration_module_fixture_skip"
        with TemporaryDirectory(prefix="integration-module-fixture-skip-") as directory:
            root = Path(directory)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / f"{module_name}.py").write_text(
                "import unittest\n"
                "def setUpModule():\n"
                "    raise unittest.SkipTest('controlled module fixture skip')\n"
                "class ModuleFixtureCase(unittest.TestCase):\n"
                "    def test_one(self): pass\n"
                "    def test_two(self): pass\n",
                encoding="utf-8",
            )
            test_ids = [
                f"{module_name}.ModuleFixtureCase.test_one",
                f"{module_name}.ModuleFixtureCase.test_two",
            ]
            result_path = root / "result.json"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "inventory_ids": test_ids,
                        "shard_ids": test_ids,
                        "shard_index": 0,
                        "shard_count": 1,
                        "result_path": str(result_path),
                    }
                ),
                encoding="utf-8",
            )
            original_path = sys.path.copy()
            try:
                with patch.object(preflight, "ROOT", root):
                    status = preflight.run_shard_worker(manifest_path)
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            finally:
                sys.modules.pop(module_name, None)
                sys.path[:] = original_path

        self.assertEqual(status, 0)
        self.assertEqual(payload["tests_run"], 2)
        self.assertEqual(payload["ran_ids"], sorted(test_ids))
        self.assertEqual(
            {outcome["status"] for outcome in payload["outcomes"].values()},
            {"skipped"},
        )

    def test_skipped_subtest_keeps_the_discovered_parent_id(self) -> None:
        class Probe(unittest.TestCase):
            def test_skipped_subtest(self):
                with self.subTest(case="parameterized"):
                    self.skipTest("controlled skip")

        case = Probe("test_skipped_subtest")
        with (
            patch.object(preflight, "classify_test_inventory", return_value=([], [case.id()])),
            redirect_stdout(io.StringIO()) as output,
        ):
            status = preflight.run_discovered_tests([case], jobs=2, verbosity=0)

        self.assertEqual(status, 0)
        self.assertIn("tests_run=1 passed=0 skipped=1 failures=0 errors=0", output.getvalue())
        self.assertNotIn("omitted test IDs", output.getvalue())

    def test_parallel_worker_budget_is_capped_by_schedulable_modules(self) -> None:
        cases = []
        for module, method in (
            ("test_alpha", "test_one"),
            ("test_alpha", "test_two"),
            ("test_beta", "test_one"),
            ("test_beta", "test_two"),
        ):
            case_type = type(
                "Case",
                (unittest.TestCase,),
                {"__module__": module, method: lambda self: None},
            )
            cases.append(case_type(method))
        test_ids = [case.id() for case in cases]
        outcomes = {test_id: {"status": "passed"} for test_id in test_ids}
        metrics = {
            "runner_wall_seconds": 0.01,
            "slowest_shard_seconds": 0.01,
            "worker_seconds": 0.02,
            "estimated_idle_worker_seconds": 0.0,
        }
        with (
            patch.object(preflight, "classify_test_inventory", return_value=(test_ids, [])),
            patch.object(
                preflight,
                "run_parallel_shards",
                return_value=(outcomes, [], metrics),
            ) as run_parallel,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = preflight.run_discovered_tests(cases, jobs=100, verbosity=0)

        self.assertEqual(status, 0)
        self.assertEqual(run_parallel.call_args.args[2], 2)
        self.assertIn("requested=100 effective=2", output.getvalue())
        self.assertIn("peak_workers=2", output.getvalue())

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
        self.assertEqual(preflight.parse_args(["fast", "--jobs", "1"]).jobs, 1)

    def test_jobs_must_be_positive(self) -> None:
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                preflight.parse_args(["fast", "--jobs", value])

    def test_worker_environment_drops_python_path_injection(self) -> None:
        with patch.dict(
            "os.environ",
            {"PYTHONPATH": "/unexpected", "PYTHONHOME": "/unexpected-home", "PYTHONSTARTUP": "/unexpected.py"},
            clear=False,
        ):
            environment = preflight.child_environment()
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertNotIn("PYTHONSTARTUP", environment)
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")

    def test_partition_is_deterministic_complete_and_disjoint(self) -> None:
        test_ids = [
            "test_alpha.Case.test_one",
            "test_alpha.Case.test_two",
            "test_beta.Case.test_one",
            "test_gamma.Case.test_one",
        ]
        first = preflight.partition_test_ids(test_ids, 2)
        second = preflight.partition_test_ids(test_ids, 2)
        assigned = [test_id for shard in first for test_id in shard]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(set(assigned), set(test_ids))
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(preflight.partition_test_ids(test_ids, 1), [test_ids])

    def test_new_or_changed_modules_fail_closed_to_serial_classification(self) -> None:
        with TemporaryDirectory(prefix="integration-module-classification-") as directory:
            root = Path(directory)
            tests_dir = root / "tests"
            tests_dir.mkdir()

            def make_case(module: str) -> unittest.TestCase:
                case_type = type(
                    "Probe",
                    (unittest.TestCase,),
                    {"__module__": module, "test_probe": lambda self: None},
                )
                return case_type("test_probe")

            reviewed_case = make_case("test_reviewed")
            changed_case = make_case("test_changed")
            new_case = make_case("test_new")
            cases = [reviewed_case, changed_case, new_case]
            for module in ("test_reviewed", "test_changed", "test_new"):
                (tests_dir / f"{module}.py").write_text("# fixture module\n", encoding="utf-8")

            reviewed_source = (tests_dir / "test_reviewed.py").read_bytes()
            manifest_path = root / "parallel-modules.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "parallel_module_sha256": {
                            "test_reviewed": {
                                "source_sha256": hashlib.sha256(reviewed_source).hexdigest(),
                                "test_ids_sha256": preflight.test_id_digest([reviewed_case.id()]),
                            },
                            "test_changed": {
                                "source_sha256": "0" * 64,
                                "test_ids_sha256": preflight.test_id_digest([changed_case.id()]),
                            },
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            with (
                patch.object(preflight, "ROOT", root),
                patch.object(preflight, "PARALLEL_MODULE_MANIFEST", manifest_path),
            ):
                parallel, serial = preflight.classify_test_inventory(cases)

        all_ids = [case.id() for case in cases]
        self.assertEqual(set(parallel) | set(serial), set(all_ids))
        self.assertFalse(set(parallel) & set(serial))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(parallel, [reviewed_case.id()])
        self.assertEqual(serial, [changed_case.id(), new_case.id()])

    def test_shard_failure_propagates_after_all_workers_join(self) -> None:
        test_ids = [
            "test_alpha.Case.test_one",
            "test_beta.Case.test_two",
        ]
        barrier = Barrier(2)
        calls = []

        def fake_subprocess_run(command, **kwargs):
            manifest_path = Path(command[-1])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            barrier.wait(timeout=5)
            outcomes = {test_id: {"status": "passed"} for test_id in manifest["shard_ids"]}
            payload = {
                "shard_index": manifest["shard_index"],
                "ran_ids": sorted(outcomes),
                "outcomes": outcomes,
                "tests_run": len(outcomes),
                "outcome_sha256": preflight.outcome_digest(outcomes),
            }
            Path(manifest["result_path"]).write_text(json.dumps(payload), encoding="utf-8")
            calls.append(manifest["shard_index"])
            return type("Completed", (), {"returncode": 7 if manifest["shard_index"] == 1 else 0, "stdout": "", "stderr": ""})()

        with patch.object(preflight.subprocess, "run", side_effect=fake_subprocess_run):
            outcomes, failures, _metrics = preflight.run_parallel_shards(test_ids, test_ids, 2, 0)
        self.assertEqual(sorted(calls), [0, 1])
        self.assertEqual(set(outcomes), set(test_ids))
        self.assertTrue(any("exited with 7" in failure for failure in failures))


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

    def test_provider_preparation_respects_budget_and_uses_distinct_targets(self) -> None:
        barrier = Barrier(2)
        lock = Lock()
        state = {"active": 0, "peak": 0, "calls": 0}

        def fake_clone(_source, _revision, target, _label):
            with lock:
                state["calls"] += 1
                ordinal = state["calls"]
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            if ordinal <= 2:
                barrier.wait(timeout=5)
            with lock:
                state["active"] -= 1
            return target

        providers = [
            (name, Path(f"/provider/{name}"), "a" * 40)
            for name in ("composition", "policy", "modeling")
        ]
        with patch.object(preflight, "clone_provider_for_materialization", side_effect=fake_clone):
            prepared = preflight.prepare_provider_checkouts(providers, Path("/materialized"), jobs=2)
        self.assertEqual(state["calls"], 3)
        self.assertEqual(state["peak"], 2)
        self.assertEqual(set(prepared), {"composition", "policy", "modeling"})
        self.assertEqual(len(set(prepared.values())), 3)

    def test_provider_metrics_report_observed_peak_below_configured_cap(self) -> None:
        from concurrent.futures import ThreadPoolExecutor as RealThreadPoolExecutor

        providers = [
            (name, Path(f"/provider/{name}"), "a" * 40)
            for name in ("composition", "policy", "modeling")
        ]

        def single_worker_executor(*, max_workers, thread_name_prefix):
            self.assertEqual(max_workers, 3)
            return RealThreadPoolExecutor(max_workers=1, thread_name_prefix=thread_name_prefix)

        with (
            patch.object(preflight, "clone_provider_for_materialization", side_effect=lambda _s, _r, target, _l: target),
            patch.object(preflight, "ThreadPoolExecutor", side_effect=single_worker_executor),
            redirect_stdout(io.StringIO()) as output,
        ):
            prepared = preflight.prepare_provider_checkouts(
                providers, Path("/materialized"), jobs=3
            )

        self.assertEqual(set(prepared), {"composition", "policy", "modeling"})
        metrics = next(
            line
            for line in output.getvalue().splitlines()
            if line.startswith("INTEGRATION_PROVIDER_METRICS ")
        )
        self.assertIn("requested=3 effective=3", metrics)
        self.assertIn("peak_workers=1", metrics)

    def test_provider_preparation_failure_waits_for_other_workers(self) -> None:
        barrier = Barrier(2)
        lock = Lock()
        state = {"calls": 0}

        def fake_clone(_source, _revision, target, label):
            with lock:
                state["calls"] += 1
                ordinal = state["calls"]
            if ordinal <= 2:
                barrier.wait(timeout=5)
            if label.startswith("policy"):
                time.sleep(0.05)
                raise RuntimeError("controlled clone failure")
            return target

        providers = [
            (name, Path(f"/provider/{name}"), "a" * 40)
            for name in ("composition", "policy", "modeling")
        ]
        with patch.object(preflight, "clone_provider_for_materialization", side_effect=fake_clone):
            with redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(preflight.PreflightFailure, "controlled clone failure"):
                    preflight.prepare_provider_checkouts(providers, Path("/materialized"), jobs=2)
        self.assertEqual(state["calls"], 3)
        metrics = next(
            line
            for line in output.getvalue().splitlines()
            if line.startswith("INTEGRATION_PROVIDER_METRICS ")
        )
        worker_seconds = float(
            next(field.split("=", 1)[1] for field in metrics.split() if field.startswith("worker_seconds="))
        )
        slowest_worker_seconds = float(
            next(
                field.split("=", 1)[1]
                for field in metrics.split()
                if field.startswith("slowest_worker_seconds=")
            )
        )
        self.assertGreaterEqual(worker_seconds, 0.04)
        self.assertGreaterEqual(slowest_worker_seconds, 0.04)


    def test_discovery_fails_if_a_test_import_is_not_represented(self) -> None:
        self.assertGreaterEqual(preflight.validate_discovery(), 43)
