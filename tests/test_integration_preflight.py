from __future__ import annotations

from pathlib import Path
import json
from threading import Barrier, Lock
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
        cases = preflight.discover_test_cases()
        parallel, serial = preflight.classify_test_inventory(cases)
        all_ids = [case.id() for case in cases]
        self.assertEqual(set(parallel) | set(serial), set(all_ids))
        self.assertFalse(set(parallel) & set(serial))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertTrue(all(test_id.startswith("test_integration_preflight.") for test_id in serial))
        self.assertEqual(len(parallel), 141)

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
                raise RuntimeError("controlled clone failure")
            return target

        providers = [
            (name, Path(f"/provider/{name}"), "a" * 40)
            for name in ("composition", "policy", "modeling")
        ]
        with patch.object(preflight, "clone_provider_for_materialization", side_effect=fake_clone):
            with self.assertRaisesRegex(preflight.PreflightFailure, "controlled clone failure"):
                preflight.prepare_provider_checkouts(providers, Path("/materialized"), jobs=2)
        self.assertEqual(state["calls"], 3)


    def test_discovery_fails_if_a_test_import_is_not_represented(self) -> None:
        self.assertGreaterEqual(preflight.validate_discovery(), 43)
