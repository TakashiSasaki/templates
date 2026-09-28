from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sys
from threading import Barrier, Lock
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import qualify  # noqa: E402


class QualificationWorkerBudgetTests(unittest.TestCase):
    def test_skipped_subtest_uses_the_discovered_parent_id(self) -> None:
        class Probe(unittest.TestCase):
            def test_skipped_subtest(self):
                with self.subTest(case="child"):
                    self.skipTest("not available")

        case = Probe("test_skipped_subtest")
        result = qualify.run_suite([case], verbosity=0)
        self.assertEqual(
            result.outcomes,
            {case.id(): {"status": "skipped", "reason": "not available"}},
        )
        self.assertEqual(qualify.outcome_digest(result.outcomes), qualify.outcome_digest({
            case.id(): {"status": "skipped", "reason": "not available"},
        }))

    def test_subtest_assertion_and_error_are_classified_separately(self) -> None:
        class AssertionProbe(unittest.TestCase):
            def test_subtest_assertion(self):
                with self.subTest(case="assertion"):
                    self.assertEqual(1, 2)

        class ErrorProbe(unittest.TestCase):
            def test_subtest_error(self):
                with self.subTest(case="runtime"):
                    raise RuntimeError("unexpected runtime error")

        assertion = AssertionProbe("test_subtest_assertion")
        error = ErrorProbe("test_subtest_error")
        assertion_result = qualify.run_suite([assertion], verbosity=0)
        error_result = qualify.run_suite([error], verbosity=0)
        self.assertEqual(assertion_result.outcomes, {assertion.id(): {"status": "failure"}})
        self.assertEqual(error_result.outcomes, {error.id(): {"status": "error"}})
        self.assertEqual(
            qualify.outcome_digest(assertion_result.outcomes),
            qualify.outcome_digest({assertion.id(): {"status": "failure"}}),
        )
        self.assertEqual(
            qualify.outcome_digest(error_result.outcomes),
            qualify.outcome_digest({error.id(): {"status": "error"}}),
        )

    def test_mixed_subtest_error_has_stable_error_precedence(self) -> None:
        class MixedSubtestProbe(unittest.TestCase):
            def __init__(self, method_name="test_mixed_subtests", *, reverse=False):
                super().__init__(method_name)
                self.reverse = reverse

            def test_mixed_subtests(self):
                exceptions = [AssertionError("assertion"), RuntimeError("runtime")]
                if self.reverse:
                    exceptions.reverse()
                for exception in exceptions:
                    with self.subTest(kind=type(exception).__name__):
                        raise exception

        for reverse in (False, True):
            case = MixedSubtestProbe(reverse=reverse)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = qualify.run_suite([case], verbosity=0)
            self.assertEqual(result.outcomes[case.id()], {"status": "error"})
            self.assertEqual(qualify.outcome_counts(result.outcomes)["errors"], 1)

    def test_serial_result_reports_expected_failure_and_unexpected_success_counts(self):
        class ExpectedFailure(unittest.TestCase):
            @unittest.expectedFailure
            def test_expected_failure(self):
                self.fail("expected")

        class UnexpectedSuccess(unittest.TestCase):
            @unittest.expectedFailure
            def test_unexpected_success(self):
                pass

        cases = [
            ExpectedFailure("test_expected_failure"),
            UnexpectedSuccess("test_unexpected_success"),
        ]
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            status = qualify.run_discovered_tests(cases, 1, ROOT)

        self.assertEqual(status, 1)
        self.assertIn(
            "MODELING_TEST_RESULT tests_run=2 passed=0 skipped=0 failures=0 errors=0 "
            "expected_failures=1 unexpected_successes=1",
            output.getvalue(),
        )

    def test_parallel_result_reports_expected_failure_and_unexpected_success_counts(self):
        class ExpectedFailure(unittest.TestCase):
            def test_expected_failure(self):
                pass

        class UnexpectedSuccess(unittest.TestCase):
            def test_unexpected_success(self):
                pass

        cases = [
            ExpectedFailure("test_expected_failure"),
            UnexpectedSuccess("test_unexpected_success"),
        ]
        outcomes = {
            cases[0].id(): {"status": "expected-failure"},
            cases[1].id(): {"status": "unexpected-success"},
        }
        metrics = {
            "runner_wall_seconds": 0.01,
            "slowest_shard_seconds": 0.01,
            "worker_seconds": 0.02,
            "estimated_idle_worker_seconds": 0.0,
        }
        with (
            patch.object(qualify, "classify_inventory", return_value=([case.id() for case in cases], [])),
            patch.object(qualify, "MEASURED_EFFECTIVE_WORKER_CAP", 4),
            patch.object(qualify, "run_parallel_shards", return_value=(outcomes, [], metrics)),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()),
        ):
            status = qualify.run_discovered_tests(cases, 2, ROOT)

        self.assertEqual(status, 1)
        self.assertIn(
            "MODELING_TEST_RESULT tests_run=2 passed=0 skipped=0 failures=0 errors=0 "
            "expected_failures=1 unexpected_successes=1",
            output.getvalue(),
        )

    def test_jobs_must_be_positive_and_default_to_serial(self) -> None:
        self.assertEqual(qualify.parse_args([]).jobs, 1)
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                qualify.parse_args(["--jobs", value])

    def test_exact_head_requires_full_matching_sha_and_clean_tree(self) -> None:
        head = "a" * 40
        with patch.object(qualify, "git_output", side_effect=(head, "")):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(qualify.qualification_head(ROOT, head, require_clean=True), head)
        with patch.object(qualify, "git_output", return_value=head):
            with self.assertRaisesRegex(qualify.QualificationError, "full lowercase"):
                qualify.qualification_head(ROOT, "not-a-sha")
            with self.assertRaisesRegex(qualify.QualificationError, "mismatch"):
                qualify.qualification_head(ROOT, "b" * 40)

    def test_stable_test_id_partitions_are_complete_and_disjoint(self) -> None:
        test_ids = [f"test_module.Case.test_{index:03d}" for index in range(68)]
        for jobs in (1, 2, 4):
            first = qualify.partition_test_ids(test_ids, jobs)
            second = qualify.partition_test_ids(test_ids, jobs)
            assigned = [test_id for shard in first for test_id in shard]
            with self.subTest(jobs=jobs):
                self.assertEqual(first, second)
                self.assertEqual(len(first), min(jobs, len(test_ids)))
                self.assertEqual(set(assigned), set(test_ids))
                self.assertEqual(len(assigned), len(set(assigned)))

    def test_jobs_one_runs_serial_without_spawning_shards(self) -> None:
        events = []

        class Probe(unittest.TestCase):
            def test_serial(self):
                events.append("serial")

        with patch.object(qualify, "run_parallel_shards") as parallel, redirect_stdout(io.StringIO()) as output:
            status = qualify.run_discovered_tests([Probe("test_serial")], 1, ROOT)
        self.assertEqual(status, 0)
        self.assertEqual(events, ["serial"])
        parallel.assert_not_called()
        self.assertIn("requested=1 effective=1", output.getvalue())

    def test_nested_main_does_not_inherit_private_worker_arguments(self) -> None:
        observed = []

        class Probe(unittest.TestCase):
            def test_read_cli(self):
                args = qualify.parse_args()
                observed.append((args.jobs, args.worker_manifest))

        worker_argv = ["qualify.py", "--jobs", "1", "--worker-manifest", "/tmp/private-manifest.json"]
        with patch.object(qualify.sys, "argv", worker_argv), redirect_stdout(io.StringIO()):
            qualify.run_suite_without_worker_options([Probe("test_read_cli")])
        self.assertEqual(observed, [(1, None)])

    def test_unreviewed_test_module_stays_in_serial_classification(self) -> None:
        cases = qualify.discover_test_cases(ROOT)
        parallel, serial = qualify.classify_inventory(cases, ROOT)
        all_ids = [case.id() for case in cases]
        self.assertEqual(set(parallel) | set(serial), set(all_ids))
        self.assertFalse(set(parallel) & set(serial))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertTrue(all(test_id.startswith("test_qualification_worker_budget.") for test_id in serial))
        self.assertEqual(len(parallel), 68)

    def test_changed_module_fingerprint_fails_closed_to_serial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="modeling-module-classification-") as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tools").mkdir()
            shutil.copyfile(
                ROOT / "tools/qualification_parallel_test_modules.json",
                root / "tools/qualification_parallel_test_modules.json",
            )
            (root / "tests/test_catalog.py").write_text("# changed source", encoding="utf-8")

            ChangedCatalogTest = type(
                "ChangedCatalogTest",
                (unittest.TestCase,),
                {"__module__": "test_catalog", "test_added_after_review": lambda self: None},
            )
            case = ChangedCatalogTest("test_added_after_review")
            parallel, serial = qualify.classify_inventory([case], root)
        self.assertEqual(parallel, [])
        self.assertEqual(serial, [case.id()])

    def test_serial_lane_starts_after_all_parallel_shards_finish(self) -> None:
        events = []

        class Probe(unittest.TestCase):
            def test_parallel_one(self):
                self.fail("parallel tests are represented by the controlled child result")

            def test_parallel_two(self):
                self.fail("parallel tests are represented by the controlled child result")

            def test_serial(self):
                events.append("serial")

        cases = [Probe("test_parallel_one"), Probe("test_parallel_two"), Probe("test_serial")]
        parallel_ids = [cases[0].id(), cases[1].id()]
        serial_ids = [cases[2].id()]

        def finish_shards(inventory_ids, assigned_ids, jobs, _head_sha=None):
            self.assertEqual(set(inventory_ids), set(c.id() for c in cases))
            self.assertEqual(set(assigned_ids), set(parallel_ids))
            self.assertEqual(jobs, 2)
            events.append("parallel-finished")
            return (
                {test_id: {"status": "passed"} for test_id in parallel_ids},
                [],
                {"runner_wall_seconds": 0.01, "slowest_shard_seconds": 0.01,
                 "worker_seconds": 0.02, "estimated_idle_worker_seconds": 0.0},
            )

        with (
            patch.object(qualify, "MEASURED_EFFECTIVE_WORKER_CAP", 4),
            patch.object(qualify, "classify_inventory", return_value=(parallel_ids, serial_ids)),
            patch.object(qualify, "run_parallel_shards", side_effect=finish_shards),
            redirect_stdout(io.StringIO()) as output,
        ):
            status = qualify.run_discovered_tests(cases, 4, ROOT)
        self.assertEqual(status, 0)
        self.assertEqual(events, ["parallel-finished", "serial"])
        self.assertIn("requested=4 effective=2", output.getvalue())

    def test_worker_environment_drops_python_path_injection(self) -> None:
        with patch.dict(
            os.environ,
            {"PYTHONPATH": "/unexpected", "PYTHONHOME": "/unexpected-home", "PYTHONSTARTUP": "/unexpected.py"},
            clear=False,
        ):
            environment = qualify.worker_environment()
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertNotIn("PYTHONSTARTUP", environment)
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")

    def test_shard_child_failure_propagates_after_every_worker_joins(self) -> None:
        test_ids = ["test_alpha.Case.test_one", "test_beta.Case.test_two"]
        barrier = Barrier(2)
        lock = Lock()
        completed = []

        def fake_subprocess_run(command, **_kwargs):
            manifest_path = Path(command[-1])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            barrier.wait(timeout=5)
            outcomes = {test_id: {"status": "passed"} for test_id in manifest["shard_ids"]}
            Path(manifest["result_path"]).write_text(json.dumps({
                "shard_index": manifest["shard_index"],
                "ran_ids": sorted(outcomes),
                "outcomes": outcomes,
                "tests_run": len(outcomes),
                "outcome_sha256": qualify.outcome_digest(outcomes),
            }), encoding="utf-8")
            with lock:
                completed.append(manifest["shard_index"])
            return type(
                "Completed",
                (),
                {"returncode": 9 if manifest["shard_index"] == 1 else 0, "stdout": "", "stderr": ""},
            )()

        with patch.object(qualify.subprocess, "run", side_effect=fake_subprocess_run):
            outcomes, failures, _metrics = qualify.run_parallel_shards(test_ids, test_ids, 2)
        self.assertEqual(sorted(completed), [0, 1])
        self.assertEqual(set(outcomes), set(test_ids))
        self.assertTrue(any("exited with 9" in failure for failure in failures))
