#!/usr/bin/env python3
"""L1 core repository test runner and classification boundary.

Classifies and executes repository unit and contract tests according to the staged CI model:
- L1 Core Validation: Pure repository-owned unit and contract tests (Markdown contracts,
  reader projections, authority models, navigation graphs, glossary contracts, translation
  manifests, site links, public URL boundaries, workflow boundaries, and classifiers).
  Executes without external provider checkouts or external browser binaries.
- L2 Integration: Provider-dependent tests (requiring checked-out and materialized
  composition/policy providers). Node and browser acceptance are owned by their
  dedicated workflow scripts rather than this Python module classifier.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Tests that strictly require checked-out and materialized external provider checkouts.
PROVIDER_INTEGRATION_MODULES = (
    frozenset()
)  # Provider qualification belongs to Integration.
PARALLEL_MODULE_MANIFEST = Path(__file__).with_name("site_parallel_test_modules.json")
MEASURED_EFFECTIVE_WORKER_CAP = 1


def get_default_tests_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "tests"


def classify_test_modules(
    tests_dir: Path | None = None,
) -> dict[str, list[str]]:
    if tests_dir is None:
        tests_dir = get_default_tests_dir()

    all_modules = sorted([f.stem for f in tests_dir.glob("test_*.py")])
    core = []
    provider = []

    for mod in all_modules:
        if mod in PROVIDER_INTEGRATION_MODULES:
            provider.append(mod)
        else:
            core.append(mod)

    return {
        "core": core,
        "provider": provider,
    }


def load_test_suite(
    suite_name: str = "core",
    tests_dir: Path | None = None,
    module_names: set[str] | None = None,
) -> unittest.TestSuite:
    if tests_dir is None:
        tests_dir = get_default_tests_dir()

    repo_root = tests_dir.parent
    for p in (str(tests_dir), str(repo_root)):
        if p not in sys.path:
            sys.path.insert(0, p)

    categories = classify_test_modules(tests_dir)
    if suite_name == "core":
        selected = categories["core"]
    elif suite_name == "provider":
        selected = categories["provider"]
    elif suite_name == "integration":
        selected = sorted(categories["provider"])
    elif suite_name == "all":
        selected = sorted(categories["core"] + categories["provider"])
    else:
        raise ValueError(f"Unknown test suite: {suite_name!r}")

    if module_names is not None:
        unknown_modules = module_names - set(selected)
        if unknown_modules:
            raise ValueError(
                f"worker requested modules outside the {suite_name!r} suite: {sorted(unknown_modules)}"
            )
        selected = [module for module in selected if module in module_names]

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for mod_name in selected:
        mod = __import__(mod_name)
        suite.addTests(loader.loadTestsFromModule(mod))
    return suite


def flatten_suite(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    cases: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            cases.extend(flatten_suite(item))
        else:
            cases.append(item)
    return cases


def test_id_digest(test_ids: list[str] | tuple[str, ...]) -> str:
    encoded = "\n".join(sorted(test_ids)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_parallel_module_manifest(
    manifest_path: Path = PARALLEL_MODULE_MANIFEST,
) -> dict[str, dict[str, str]]:
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "parallel_module_sha256",
    }:
        raise ValueError("Site parallel-test module manifest has unsupported fields")
    if value["schema_version"] != 1 or not isinstance(
        value["parallel_module_sha256"], dict
    ):
        raise ValueError("Site parallel-test module manifest has an unsupported schema")
    modules = value["parallel_module_sha256"]
    if any(
        not isinstance(name, str)
        or not name.startswith("test_")
        or not isinstance(fingerprints, dict)
        or set(fingerprints) != {"source_sha256", "test_ids_sha256"}
        or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in fingerprints.values()
        )
        for name, fingerprints in modules.items()
    ):
        raise ValueError(
            "Site parallel-test module manifest contains an invalid module fingerprint"
        )
    return modules


def classify_test_inventory(
    test_ids: list[str] | tuple[str, ...],
    *,
    tests_dir: Path | None = None,
    manifest_path: Path = PARALLEL_MODULE_MANIFEST,
) -> tuple[list[str], list[str]]:
    if len(set(test_ids)) != len(test_ids):
        raise ValueError("Site unittest discovery returned duplicate test IDs")
    if tests_dir is None:
        tests_dir = get_default_tests_dir()
    reviewed = load_parallel_module_manifest(manifest_path)
    modules = {test_id.split(".", 1)[0] for test_id in test_ids}
    parallel_modules = set()
    for module, module_ids in (
        (name, [test_id for test_id in test_ids if test_id.split(".", 1)[0] == name])
        for name in modules
    ):
        expected = reviewed.get(module)
        module_path = tests_dir / f"{module}.py"
        if expected is None or not module_path.is_file():
            continue
        source_digest = hashlib.sha256(module_path.read_bytes()).hexdigest()
        if (
            source_digest == expected["source_sha256"]
            and test_id_digest(module_ids) == expected["test_ids_sha256"]
        ):
            parallel_modules.add(module)
    parallel = [
        test_id for test_id in test_ids if test_id.split(".", 1)[0] in parallel_modules
    ]
    serial = [
        test_id
        for test_id in test_ids
        if test_id.split(".", 1)[0] not in parallel_modules
    ]
    if set(parallel) & set(serial) or set(parallel) | set(serial) != set(test_ids):
        raise ValueError(
            "Site unittest parallel and serial classifications are incomplete or overlapping"
        )
    return parallel, serial


def partition_test_ids(
    test_ids: list[str] | tuple[str, ...], jobs: int
) -> list[list[str]]:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    if len(set(test_ids)) != len(test_ids):
        raise ValueError("cannot shard duplicate Site unittest IDs")
    if not test_ids:
        return []
    worker_count = min(jobs, len(test_ids))
    ordered = sorted(
        test_ids,
        key=lambda test_id: (
            hashlib.sha256(test_id.encode("utf-8")).hexdigest(),
            test_id,
        ),
    )
    shards = [[] for _ in range(worker_count)]
    for index, test_id in enumerate(ordered):
        shards[index % worker_count].append(test_id)
    return shards


class InventoryTextTestResult(unittest.TextTestResult):
    """Text result that records an exact outcome classification per test ID."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: dict[str, dict[str, str]] = {}

    def _record(
        self, test: unittest.TestCase, status: str, reason: str | None = None
    ) -> None:
        test_id = test.id()
        existing = self.outcomes.get(test_id)
        if existing is not None and existing["status"] in {
            "failure",
            "error",
            "unexpected-success",
        }:
            return
        value = {"status": status}
        if reason is not None:
            value["reason"] = str(reason)
        self.outcomes[test_id] = value

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failure")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected-failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected-success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(test, "failure")


class InventoryTextTestRunner(unittest.TextTestRunner):
    resultclass = InventoryTextTestResult


def run_suite(
    cases: list[unittest.TestCase],
    verbosity: int,
) -> InventoryTextTestResult:
    result = InventoryTextTestRunner(verbosity=verbosity).run(unittest.TestSuite(cases))
    return result


def outcome_digest(outcomes: dict[str, dict[str, str]]) -> str:
    encoded = json.dumps(
        outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def summarize_outcomes(outcomes: dict[str, dict[str, str]]) -> dict[str, int]:
    counts = Counter(value["status"] for value in outcomes.values())
    return {
        "passed": counts["passed"],
        "skipped": counts["skipped"],
        "failures": counts["failure"],
        "errors": counts["error"],
        "expected_failures": counts["expected-failure"],
        "unexpected_successes": counts["unexpected-success"],
    }


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        if environment.pop(name, None) is not None:
            print(f"SITE_ENV_SANITIZED variable={name} runner=site-python", flush=True)
    return environment


def sanitize_execution_environment() -> None:
    """Remove ambient runner injection before importing or executing test cases."""
    node_options = os.environ.pop("NODE_OPTIONS", None)
    if node_options is not None:
        print(
            "SITE_ENV_SANITIZED variable=NODE_OPTIONS runner=site-python reason=explicit-worker-budget",
            flush=True,
        )
    python_path = os.environ.pop("PYTHONPATH", None)
    if python_path is not None:
        injected_paths = {
            str(Path(entry or os.curdir).resolve())
            for entry in python_path.split(os.pathsep)
        }
        sys.path[:] = [
            entry
            for entry in sys.path
            if str(Path(entry or os.curdir).resolve()) not in injected_paths
        ]
        print(
            "SITE_ENV_SANITIZED variable=PYTHONPATH runner=site-python reason=explicit-worker-budget",
            flush=True,
        )
    for name in ("PYTHONHOME", "PYTHONSTARTUP"):
        if os.environ.pop(name, None) is not None:
            print(
                f"SITE_ENV_SANITIZED variable={name} runner=site-python reason=explicit-worker-budget",
                flush=True,
            )


def run_shard_worker(
    manifest_path: Path,
    *,
    suite_name: str,
    verbosity: int,
    cases: list[unittest.TestCase],
) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "suite",
        "inventory_ids",
        "shard_ids",
        "shard_index",
        "shard_count",
        "result_path",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest["schema_version"] != 1
    ):
        raise ValueError("Site unittest shard manifest is malformed")
    if manifest["suite"] != suite_name:
        raise ValueError("Site unittest shard suite does not match its parent")
    discovered_ids = [case.id() for case in cases]
    inventory_ids = manifest["inventory_ids"]
    shard_ids = manifest["shard_ids"]
    shard_index = manifest["shard_index"]
    shard_count = manifest["shard_count"]
    if (
        not isinstance(inventory_ids, list)
        or any(not isinstance(test_id, str) for test_id in inventory_ids)
        or not isinstance(shard_ids, list)
        or any(not isinstance(test_id, str) for test_id in shard_ids)
        or not isinstance(shard_index, int)
        or not isinstance(shard_count, int)
        or shard_count < 1
        or not 0 <= shard_index < shard_count
        or len(set(discovered_ids)) != len(discovered_ids)
        or len(set(inventory_ids)) != len(inventory_ids)
        or len(set(shard_ids)) != len(shard_ids)
        or not set(shard_ids) <= set(inventory_ids)
        or not set(shard_ids) <= set(discovered_ids)
    ):
        raise ValueError(
            "Site unittest shard discovery differs from its exact assigned inventory"
        )
    selected = set(shard_ids)
    selected_cases = [case for case in cases if case.id() in selected]
    if [case.id() for case in selected_cases] != [
        test_id for test_id in discovered_ids if test_id in selected
    ]:
        raise ValueError("Site unittest shard selection changed discovery order")
    print(
        f"SITE_SHARD_START shard={manifest['shard_index']}/{manifest['shard_count']} "
        f"inventory={len(inventory_ids)} selected={len(selected_cases)} "
        f"inventory_sha256={test_id_digest(inventory_ids)}",
        flush=True,
    )
    result = run_suite(selected_cases, verbosity)
    outcomes = result.outcomes
    result_path = Path(manifest["result_path"])
    if result_path.parent.resolve() != manifest_path.parent.resolve():
        raise ValueError(
            "Site unittest shard result must stay beside its private manifest"
        )
    payload = {
        "shard_index": manifest["shard_index"],
        "shard_count": manifest["shard_count"],
        "ran_ids": sorted(outcomes),
        "outcomes": outcomes,
        "tests_run": result.testsRun,
        "counts": summarize_outcomes(outcomes),
        "outcome_sha256": outcome_digest(outcomes),
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if sorted(outcomes) != sorted(shard_ids) or result.testsRun != len(shard_ids):
        print(
            "SITE_SHARD_FAIL reason=worker-test-inventory-mismatch",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"SITE_SHARD_PASS shard={manifest['shard_index']}/{manifest['shard_count']} "
        f"tests={result.testsRun} outcome_sha256={payload['outcome_sha256']}",
        flush=True,
    )
    return 0 if result.wasSuccessful() else 1


def run_parallel_shards(
    suite_name: str,
    inventory_ids: list[str],
    parallel_ids: list[str],
    jobs: int,
    verbosity: int,
    tests_dir: Path | None = None,
) -> tuple[dict[str, dict[str, str]], list[str], dict[str, float]]:
    if tests_dir is None:
        tests_dir = get_default_tests_dir()
    tests_dir = tests_dir.resolve()
    repository_root = tests_dir.parent
    shards = partition_test_ids(parallel_ids, jobs)
    effective_jobs = len(shards)
    if not shards:
        return (
            {},
            [],
            {
                "runner_wall_seconds": 0.0,
                "slowest_shard_seconds": 0.0,
                "shard_worker_seconds": 0.0,
                "estimated_idle_worker_seconds": 0.0,
            },
        )

    reports: dict[int, tuple[int, float, str, str, dict[str, object] | None]] = {}
    failures: list[str] = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="site-core-shards-") as temporary:
        temporary_root = Path(temporary)
        manifest_paths: dict[int, Path] = {}
        result_paths: dict[int, Path] = {}
        inventory_set = set(inventory_ids)
        for index, shard_ids in enumerate(shards):
            shard_set = set(shard_ids)
            ordered_shard_ids = [
                test_id for test_id in inventory_ids if test_id in shard_set
            ]
            result_path = temporary_root / f"shard-{index}-result.json"
            manifest_path = temporary_root / f"shard-{index}-manifest.json"
            manifest = {
                "schema_version": 1,
                "suite": suite_name,
                "inventory_ids": inventory_ids,
                "shard_ids": ordered_shard_ids,
                "shard_index": index,
                "shard_count": effective_jobs,
                "result_path": str(result_path),
            }
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            manifest_paths[index] = manifest_path
            result_paths[index] = result_path

        def execute(
            index: int,
        ) -> tuple[int, float, str, str, dict[str, object] | None]:
            command = [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--suite",
                suite_name,
                "--jobs",
                "1",
                "--worker-manifest",
                str(manifest_paths[index]),
                "--worker-tests-dir",
                str(tests_dir),
            ]
            if verbosity > 1:
                command.append("--verbose")
            shard_started = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=repository_root,
                env=child_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            wall = time.perf_counter() - shard_started
            report = None
            if result_paths[index].is_file():
                try:
                    report = json.loads(result_paths[index].read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    return (
                        completed.returncode or 1,
                        wall,
                        completed.stdout,
                        completed.stderr + f"\ninvalid worker result: {exc}",
                        None,
                    )
            return (
                completed.returncode,
                wall,
                completed.stdout,
                completed.stderr,
                report,
            )

        with ThreadPoolExecutor(
            max_workers=effective_jobs, thread_name_prefix="site-core-shard"
        ) as executor:
            futures = {
                executor.submit(execute, index): index
                for index in range(effective_jobs)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    reports[index] = future.result()
                except Exception as exc:
                    reports[index] = (
                        1,
                        0.0,
                        "",
                        f"worker could not complete: {exc}",
                        None,
                    )

        for index in range(effective_jobs):
            return_code, wall, stdout, stderr, report = reports[index]
            if stdout:
                print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
            if stderr:
                print(
                    stderr,
                    end="" if stderr.endswith("\n") else "\n",
                    file=sys.stderr,
                    flush=True,
                )
            expected_ids = sorted(shards[index])
            if return_code != 0:
                failures.append(
                    f"shard {index}/{effective_jobs} exited with {return_code}"
                )
            if not isinstance(report, dict) or report.get("ran_ids") != expected_ids:
                failures.append(
                    f"shard {index}/{effective_jobs} did not report its exact assigned IDs"
                )
                report = None
            if report is not None:
                run_ids = report.get("ran_ids")
                if (
                    not isinstance(run_ids, list)
                    or len(set(run_ids)) != len(run_ids)
                    or not set(run_ids) <= inventory_set
                ):
                    failures.append(
                        f"shard {index}/{effective_jobs} reported duplicate or unknown IDs"
                    )
                    report = None
            reports[index] = (return_code, wall, stdout, stderr, report)
            digest = test_id_digest(expected_ids)
            print(
                f"SITE_SHARD_RESULT shard={index}/{effective_jobs} ids_sha256={digest} "
                f"wall_seconds={wall:.3f} exit_code={return_code}",
                flush=True,
            )

        assigned_ids = [
            test_id for index in range(effective_jobs) for test_id in shards[index]
        ]
        if len(set(assigned_ids)) != len(assigned_ids) or sorted(
            assigned_ids
        ) != sorted(parallel_ids):
            failures.append(
                "Site unittest shard plan has missing or duplicate test IDs"
            )

        outcomes: dict[str, dict[str, str]] = {}
        actual_ids: list[str] = []
        shard_walls = []
        for index in range(effective_jobs):
            return_code, wall, _, _, report = reports[index]
            shard_walls.append(wall)
            if not isinstance(report, dict):
                continue
            shard_outcomes = report.get("outcomes")
            if not isinstance(shard_outcomes, dict):
                failures.append(
                    f"shard {index}/{effective_jobs} returned malformed outcomes"
                )
                continue
            for test_id, outcome in shard_outcomes.items():
                if test_id in outcomes:
                    failures.append(f"duplicate worker result for {test_id}")
                outcomes[test_id] = outcome
                actual_ids.append(test_id)
        if len(actual_ids) != len(set(actual_ids)) or sorted(actual_ids) != sorted(
            parallel_ids
        ):
            failures.append(
                "Site parallel worker results do not cover the exact parallel inventory"
            )

    runner_wall = time.perf_counter() - started
    shard_seconds = sum(shard_walls)
    metrics = {
        "runner_wall_seconds": runner_wall,
        "slowest_shard_seconds": max(shard_walls, default=0.0),
        "shard_worker_seconds": shard_seconds,
        "estimated_idle_worker_seconds": max(
            0.0, effective_jobs * runner_wall - shard_seconds
        ),
    }
    return outcomes, failures, metrics


def run_tests(
    suite_name: str = "core",
    verbosity: int = 1,
    tests_dir: Path | None = None,
    jobs: int = 1,
    worker_manifest: Path | None = None,
) -> int:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    if worker_manifest is None:
        sanitize_execution_environment()
    worker_data = None
    worker_modules = None
    if worker_manifest is not None:
        if jobs != 1:
            raise ValueError("Site shard workers must use --jobs 1")
        worker_data = json.loads(worker_manifest.read_text(encoding="utf-8"))
        if not isinstance(worker_data, dict) or not isinstance(
            worker_data.get("shard_ids"), list
        ):
            raise ValueError("Site unittest shard manifest is malformed")
        if any(
            not isinstance(test_id, str) or "." not in test_id
            for test_id in worker_data["shard_ids"]
        ):
            raise ValueError("Site unittest shard manifest contains an invalid test ID")
        worker_modules = {
            test_id.split(".", 1)[0] for test_id in worker_data["shard_ids"]
        }
    suite = load_test_suite(
        suite_name=suite_name, tests_dir=tests_dir, module_names=worker_modules
    )
    cases = flatten_suite(suite)
    inventory_ids = [case.id() for case in cases]
    if len(set(inventory_ids)) != len(inventory_ids):
        raise ValueError("Site unittest discovery returned duplicate test IDs")

    if worker_manifest is not None:
        return run_shard_worker(
            worker_manifest,
            suite_name=suite_name,
            verbosity=verbosity,
            cases=cases,
        )

    parallel_ids, serial_ids = classify_test_inventory(
        inventory_ids, tests_dir=tests_dir
    )
    print(
        f"SITE_UNITTEST_INVENTORY suite={suite_name} discovered={len(inventory_ids)} "
        f"parallel={len(parallel_ids)} serial_exclusive={len(serial_ids)} "
        f"inventory_sha256={test_id_digest(inventory_ids)} "
        f"parallel_sha256={test_id_digest(parallel_ids)} serial_sha256={test_id_digest(serial_ids)}",
        flush=True,
    )

    effective_jobs = (
        min(jobs, len(parallel_ids), MEASURED_EFFECTIVE_WORKER_CAP)
        if parallel_ids
        else 1
    )
    if effective_jobs == 1:
        runner_started = time.perf_counter()
        if jobs == 1:
            mode = "serial-baseline"
        elif not parallel_ids:
            mode = "serial-fail-closed"
        else:
            mode = "measured-serial-cap"
        print(
            f"SITE_WORKERS requested={jobs} effective=1 runner=site-python mode={mode} "
            f"measured_cap={MEASURED_EFFECTIVE_WORKER_CAP}",
            flush=True,
        )
        result = run_suite(cases, verbosity)
        runner_wall = time.perf_counter() - runner_started
        outcomes = result.outcomes
        counts = summarize_outcomes(outcomes)
        print(
            f"SITE_UNITTEST_RESULT suite={suite_name} tests_run={result.testsRun} "
            f"passed={counts['passed']} skipped={counts['skipped']} failures={counts['failures']} "
            f"errors={counts['errors']} expected_failures={counts['expected_failures']} "
            f"unexpected_successes={counts['unexpected_successes']} outcome_sha256={outcome_digest(outcomes)}",
            flush=True,
        )
        print(
            f"SITE_WORKER_METRICS requested={jobs} effective=1 peak_workers=1 "
            f"runner_wall_seconds={runner_wall:.3f} slowest_worker_seconds={runner_wall:.3f} "
            "estimated_idle_worker_seconds=0.000",
            flush=True,
        )
        if suite_name == "integration" and result.skipped:
            print(
                "Integration prerequisites missing: required cases were skipped",
                file=sys.stderr,
            )
            return 1
        return 0 if result.wasSuccessful() else 1

    print(
        f"SITE_WORKERS requested={jobs} effective={effective_jobs} runner=site-python "
        "mode=deterministic-unittest-shards",
        flush=True,
    )
    shards = partition_test_ids(parallel_ids, effective_jobs)
    print(
        f"SITE_SHARD_PLAN suite={suite_name} parallel={len(parallel_ids)} "
        f"serial_exclusive={len(serial_ids)} inventory_sha256={test_id_digest(inventory_ids)} "
        f"shards={','.join(str(len(shard)) for shard in shards)}",
        flush=True,
    )
    runner_started = time.perf_counter()
    parallel_outcomes, failures, shard_metrics = run_parallel_shards(
        suite_name,
        inventory_ids,
        parallel_ids,
        effective_jobs,
        verbosity,
        tests_dir,
    )
    serial_started = time.perf_counter()
    serial_cases = [case for case in cases if case.id() in set(serial_ids)]
    print(
        f"SITE_SERIAL_EXCLUSIVE_START suite={suite_name} tests={len(serial_cases)}",
        flush=True,
    )
    serial_result = run_suite(serial_cases, verbosity)
    serial_seconds = time.perf_counter() - serial_started
    outcomes = dict(parallel_outcomes)
    for test_id, outcome in serial_result.outcomes.items():
        if test_id in outcomes:
            failures.append(f"serial test duplicated a parallel result: {test_id}")
        outcomes[test_id] = outcome
    if len(outcomes) != len(inventory_ids) or set(outcomes) != set(inventory_ids):
        failures.append(
            "Site unittest results do not cover the exact discovered inventory"
        )
    counts = summarize_outcomes(outcomes)
    outcome_sha = outcome_digest(outcomes)
    tests_run = len(outcomes)
    runner_wall = time.perf_counter() - runner_started
    print(
        f"SITE_UNITTEST_RESULT suite={suite_name} tests_run={tests_run} "
        f"passed={counts['passed']} skipped={counts['skipped']} failures={counts['failures']} "
        f"errors={counts['errors']} expected_failures={counts['expected_failures']} "
        f"unexpected_successes={counts['unexpected_successes']} outcome_sha256={outcome_sha}",
        flush=True,
    )
    print(
        f"SITE_WORKER_METRICS requested={jobs} effective={effective_jobs} peak_shard_workers={effective_jobs} "
        f"runner_wall_seconds={runner_wall:.3f} serial_seconds={serial_seconds:.3f} "
        f"slowest_shard_seconds={shard_metrics['slowest_shard_seconds']:.3f} "
        f"shard_worker_seconds={shard_metrics['shard_worker_seconds']:.3f} "
        f"estimated_idle_worker_seconds={shard_metrics['estimated_idle_worker_seconds']:.3f}",
        flush=True,
    )
    if failures:
        for failure in failures:
            print(f"SITE_UNITTEST_FAIL {failure}", file=sys.stderr, flush=True)
    if suite_name == "integration" and counts["skipped"]:
        print(
            "Integration prerequisites missing: required cases were skipped",
            file=sys.stderr,
        )
        return 1
    return (
        0
        if serial_result.wasSuccessful()
        and not failures
        and counts["failures"] == 0
        and counts["errors"] == 0
        and counts["unexpected_successes"] == 0
        else 1
    )


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "jobs must be an integer of at least 1"
        ) from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1")
    return jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=["core", "provider", "integration", "all"],
        default="core",
        help="Test suite boundary to execute (default: core)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List test module classifications and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Run tests with higher verbosity",
    )
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        default=1,
        metavar="N",
        help="maximum worker processes assigned to the Site Python core suite (default: 1)",
    )
    parser.add_argument("--worker-manifest", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-tests-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.worker_manifest is not None and args.list:
        parser.error("--worker-manifest cannot be combined with --list")

    if args.list:
        classification = classify_test_modules()
        print("Test module classification:")
        for cat, mods in classification.items():
            print(f"  {cat} ({len(mods)} modules):")
            for m in mods:
                print(f"    - {m}")
        return 0

    return run_tests(
        suite_name=args.suite,
        verbosity=2 if args.verbose else 1,
        tests_dir=args.worker_tests_dir,
        jobs=args.jobs,
        worker_manifest=args.worker_manifest,
    )


if __name__ == "__main__":
    raise SystemExit(main())
