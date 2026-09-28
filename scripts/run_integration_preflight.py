#!/usr/bin/env python3
"""Run canonical local Integration validation without provider network access."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
PARALLEL_MODULE_MANIFEST = ROOT / "scripts/integration_parallel_test_modules.json"


class PreflightFailure(RuntimeError):
    """A named Integration preflight check failed."""


def command(*args: str) -> list[str]:
    return [str(PYTHON), *args]


def run(argv: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=cwd, check=True)


def git_output(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise PreflightFailure((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def require_exact_head(expected: str | None) -> str:
    head = git_output("rev-parse", "HEAD")
    if expected is not None and head != expected:
        raise PreflightFailure(f"exact Integration head mismatch: expected {expected}, found {head}")
    return head


def require_clean_tree() -> None:
    if git_output("status", "--porcelain=v1", "--untracked-files=all"):
        raise PreflightFailure("ready requires a clean index and working tree with no untracked files")


def flatten_suite(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    cases: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            cases.extend(flatten_suite(item))
        else:
            cases.append(item)
    return cases


def test_id_digest(test_ids: list[str] | tuple[str, ...]) -> str:
    return hashlib.sha256("\n".join(sorted(test_ids)).encode("utf-8")).hexdigest()


def test_module_name(test_id: str) -> str:
    parts = test_id.split(".")
    if len(parts) < 3:
        raise PreflightFailure(f"unittest returned a malformed test ID: {test_id!r}")
    return parts[0]


def discover_test_cases() -> list[unittest.TestCase]:
    for path in (str(ROOT), str(ROOT / "tests")):
        if path not in sys.path:
            sys.path.insert(0, path)
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test*.py")
    tests = flatten_suite(suite)
    failed_imports = [
        test.id()
        for test in tests
        if test.id().startswith("unittest.loader._FailedTest")
    ]
    if failed_imports:
        raise PreflightFailure("test discovery import failures: " + ", ".join(failed_imports))
    files = sorted((ROOT / "tests").glob("test_*.py"))
    imported_modules = {test.__class__.__module__.split(".")[-1] for test in tests}
    missing = [path.stem for path in files if path.stem not in imported_modules]
    if missing:
        raise PreflightFailure("test files not represented in discovery: " + ", ".join(missing))
    if not tests:
        raise PreflightFailure("Integration test discovery returned no tests")
    test_ids = [test.id() for test in tests]
    if len(set(test_ids)) != len(test_ids):
        raise PreflightFailure("Integration test discovery returned duplicate test IDs")
    return tests


def validate_discovery(cases: list[unittest.TestCase] | None = None) -> int:
    if cases is None:
        cases = discover_test_cases()
    files = sorted((ROOT / "tests").glob("test_*.py"))
    print(
        f"Integration test discovery: {len(cases)} cases across {len(files)} files",
        flush=True,
    )
    return len(cases)


def load_parallel_module_manifest() -> dict[str, dict[str, str]]:
    value = json.loads(PARALLEL_MODULE_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"schema_version", "parallel_module_sha256"}:
        raise PreflightFailure("Integration parallel-test manifest has unsupported fields")
    modules = value.get("parallel_module_sha256")
    if value.get("schema_version") != 1 or not isinstance(modules, dict):
        raise PreflightFailure("Integration parallel-test manifest has an unsupported schema")
    for module, fingerprints in modules.items():
        if (
            not isinstance(module, str)
            or not module.startswith("test_")
            or not isinstance(fingerprints, dict)
            or set(fingerprints) != {"source_sha256", "test_ids_sha256"}
            or any(
                not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                for digest in fingerprints.values()
            )
        ):
            raise PreflightFailure("Integration parallel-test manifest has an invalid fingerprint")
    return modules


def classify_test_inventory(
    cases: list[unittest.TestCase],
) -> tuple[list[str], list[str]]:
    test_ids = [case.id() for case in cases]
    if len(set(test_ids)) != len(test_ids):
        raise PreflightFailure("Integration unittest discovery returned duplicate IDs")
    reviewed = load_parallel_module_manifest()
    module_ids: dict[str, list[str]] = {}
    for case in cases:
        module_ids.setdefault(case.__class__.__module__.split(".")[-1], []).append(case.id())
    parallel_modules = set()
    for module, ids in module_ids.items():
        expected = reviewed.get(module)
        path = ROOT / "tests" / f"{module}.py"
        if expected is None or not path.is_file():
            continue
        if (
            hashlib.sha256(path.read_bytes()).hexdigest() == expected["source_sha256"]
            and test_id_digest(ids) == expected["test_ids_sha256"]
        ):
            parallel_modules.add(module)
    parallel = [case.id() for case in cases if case.__class__.__module__.split(".")[-1] in parallel_modules]
    serial = [test_id for test_id in test_ids if test_id not in set(parallel)]
    if set(parallel) & set(serial) or set(parallel) | set(serial) != set(test_ids):
        raise PreflightFailure("Integration test execution classes are incomplete or overlapping")
    return parallel, serial


def partition_test_ids(test_ids: list[str] | tuple[str, ...], jobs: int) -> list[list[str]]:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    if len(set(test_ids)) != len(test_ids):
        raise ValueError("cannot shard duplicate Integration test IDs")
    if not test_ids:
        return []
    grouped: dict[str, list[str]] = {}
    for test_id in test_ids:
        grouped.setdefault(test_module_name(test_id), []).append(test_id)
    worker_count = min(jobs, len(grouped))
    shards: list[list[str]] = [[] for _ in range(worker_count)]
    assigned: dict[str, int] = {}
    loads = [0] * worker_count
    for module in sorted(grouped, key=lambda name: (-len(grouped[name]), name)):
        worker = min(range(worker_count), key=lambda index: (loads[index], index))
        assigned[module] = worker
        loads[worker] += len(grouped[module])
    for test_id in test_ids:
        shards[assigned[test_module_name(test_id)]].append(test_id)
    return shards


class InventoryTextTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: dict[str, dict[str, str]] = {}
        self.discovered_cases: tuple[unittest.TestCase, ...] = ()

    def _record(self, test: unittest.TestCase, status: str, reason: str | None = None) -> None:
        self._record_id(test.id(), status, reason)

    def _record_id(self, test_id: str, status: str, reason: str | None = None) -> None:
        value = {"status": status}
        if reason is not None:
            value["reason"] = str(reason)
        self.outcomes[test_id] = value

    def _fixture_skip_test_ids(self, fixture_id: str) -> tuple[str, ...] | None:
        if fixture_id.startswith("setUpModule (") and fixture_id.endswith(")"):
            module = fixture_id[len("setUpModule (") : -1]
            return tuple(
                case.id()
                for case in self.discovered_cases
                if case.__class__.__module__ == module
            )
        if fixture_id.startswith("setUpClass (") and fixture_id.endswith(")"):
            target = fixture_id[len("setUpClass (") : -1]
            return tuple(
                case.id()
                for case in self.discovered_cases
                if f"{case.__class__.__module__}.{case.__class__.__qualname__}" == target
            )
        return None

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        fixture_test_ids = self._fixture_skip_test_ids(test.id())
        if fixture_test_ids is not None:
            if fixture_test_ids:
                for test_id in fixture_test_ids:
                    self._record_id(test_id, "skipped", reason)
            else:
                self._record(test, "skipped", reason)
            return
        self._record(getattr(test, "test_case", test), "skipped", reason)

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

    def __init__(self, *args, discovered_cases: list[unittest.TestCase], **kwargs):
        super().__init__(*args, **kwargs)
        self.discovered_cases = tuple(discovered_cases)

    def _makeResult(self):
        result = super()._makeResult()
        result.discovered_cases = self.discovered_cases
        return result


def run_suite(cases: list[unittest.TestCase], verbosity: int) -> InventoryTextTestResult:
    return InventoryTextTestRunner(
        verbosity=verbosity, discovered_cases=cases
    ).run(unittest.TestSuite(cases))


def outcome_digest(outcomes: dict[str, dict[str, str]]) -> str:
    return hashlib.sha256(
        json.dumps(outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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


def load_test_cases_for_modules(
    module_names: list[str], *, tests_dir: Path | None = None
) -> list[unittest.TestCase]:
    if tests_dir is None:
        tests_dir = ROOT / "tests"
    root = tests_dir.parent
    for path in (str(root), str(tests_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    loader = unittest.TestLoader()
    cases = []
    for module in module_names:
        cases.extend(flatten_suite(loader.loadTestsFromModule(importlib.import_module(module))))
    return cases


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        if environment.pop(name, None) is not None:
            print(f"INTEGRATION_ENV_SANITIZED variable={name}", flush=True)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_shard_worker(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"schema_version", "inventory_ids", "shard_ids", "shard_index", "shard_count", "result_path"}
    if not isinstance(manifest, dict) or set(manifest) != required or manifest["schema_version"] != 1:
        raise PreflightFailure("Integration shard manifest is malformed")
    inventory_ids = manifest["inventory_ids"]
    shard_ids = manifest["shard_ids"]
    if (
        not isinstance(inventory_ids, list)
        or any(not isinstance(test_id, str) for test_id in inventory_ids)
        or not isinstance(shard_ids, list)
        or any(not isinstance(test_id, str) for test_id in shard_ids)
        or len(set(inventory_ids)) != len(inventory_ids)
        or len(set(shard_ids)) != len(shard_ids)
        or not set(shard_ids) <= set(inventory_ids)
    ):
        raise PreflightFailure("Integration shard manifest contains invalid test IDs")
    modules = list(dict.fromkeys(test_module_name(test_id) for test_id in shard_ids))
    cases = load_test_cases_for_modules(modules)
    discovered_ids = [case.id() for case in cases]
    if len(set(discovered_ids)) != len(discovered_ids) or set(discovered_ids) != set(shard_ids):
        raise PreflightFailure("Integration shard imports differ from its exact assigned IDs")
    print(
        f"INTEGRATION_SHARD_START shard={manifest['shard_index']}/{manifest['shard_count']} "
        f"tests={len(shard_ids)} ids_sha256={test_id_digest(shard_ids)}",
        flush=True,
    )
    result = run_suite(cases, 2)
    result_path = Path(manifest["result_path"])
    if result_path.parent.resolve() != manifest_path.parent.resolve():
        raise PreflightFailure("Integration shard result must stay beside its private manifest")
    payload = {
        "shard_index": manifest["shard_index"],
        "ran_ids": sorted(result.outcomes),
        "outcomes": result.outcomes,
        "tests_run": len(result.outcomes),
        "outcome_sha256": outcome_digest(result.outcomes),
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if len(result.outcomes) != len(shard_ids) or sorted(result.outcomes) != sorted(shard_ids):
        return 1
    return 0 if result.wasSuccessful() else 1


def run_parallel_shards(
    inventory_ids: list[str], parallel_ids: list[str], jobs: int, verbosity: int
) -> tuple[dict[str, dict[str, str]], list[str], dict[str, float]]:
    shards = partition_test_ids(parallel_ids, jobs)
    if not shards:
        return {}, [], {"runner_wall_seconds": 0.0, "slowest_shard_seconds": 0.0, "worker_seconds": 0.0, "estimated_idle_worker_seconds": 0.0}
    effective_jobs = len(shards)
    reports: dict[int, tuple[int, float, str, str, dict[str, object] | None]] = {}
    failures: list[str] = []
    runner_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="integration-unittest-shards-") as directory:
        temporary_root = Path(directory)
        manifests = {}
        results = {}
        for index, shard_ids in enumerate(shards):
            result_path = temporary_root / f"shard-{index}-result.json"
            manifest_path = temporary_root / f"shard-{index}-manifest.json"
            manifest_path.write_text(json.dumps({
                "schema_version": 1,
                "inventory_ids": inventory_ids,
                "shard_ids": shard_ids,
                "shard_index": index,
                "shard_count": effective_jobs,
                "result_path": str(result_path),
            }, sort_keys=True) + "\n", encoding="utf-8")
            manifests[index] = manifest_path
            results[index] = result_path

        def execute(index: int):
            command_line = [
                sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                "fast", "--jobs", "1", "--worker-manifest", str(manifests[index]),
            ]
            started = time.perf_counter()
            completed = subprocess.run(
                command_line,
                cwd=ROOT,
                env=child_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            wall = time.perf_counter() - started
            report = None
            if results[index].is_file():
                try:
                    report = json.loads(results[index].read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    return completed.returncode or 1, wall, completed.stdout, completed.stderr + f"\ninvalid result: {exc}", None
            return completed.returncode, wall, completed.stdout, completed.stderr, report

        with ThreadPoolExecutor(max_workers=effective_jobs, thread_name_prefix="integration-test-shard") as executor:
            futures = {executor.submit(execute, index): index for index in range(effective_jobs)}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    reports[index] = future.result()
                except Exception as exc:
                    reports[index] = (1, 0.0, "", f"worker could not complete: {exc}", None)
        for index in range(effective_jobs):
            return_code, wall, stdout, stderr, report = reports[index]
            if stdout:
                print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
            if stderr:
                print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
            if return_code != 0:
                failures.append(f"shard {index}/{effective_jobs} exited with {return_code}")
            if not isinstance(report, dict) or report.get("ran_ids") != sorted(shards[index]):
                failures.append(f"shard {index}/{effective_jobs} omitted or duplicated assigned IDs")
                report = None
            reports[index] = (return_code, wall, stdout, stderr, report)
            print(
                f"INTEGRATION_SHARD_RESULT shard={index}/{effective_jobs} "
                f"ids_sha256={test_id_digest(shards[index])} wall_seconds={wall:.3f} exit_code={return_code}",
                flush=True,
            )
        assigned = [test_id for shard in shards for test_id in shard]
        if len(assigned) != len(set(assigned)) or sorted(assigned) != sorted(parallel_ids):
            failures.append("Integration shard plan has missing or duplicate IDs")
        outcomes = {}
        actual_ids = []
        walls = []
        for index in range(effective_jobs):
            _rc, wall, _stdout, _stderr, report = reports[index]
            walls.append(wall)
            if not isinstance(report, dict) or not isinstance(report.get("outcomes"), dict):
                failures.append(f"shard {index}/{effective_jobs} returned malformed outcomes")
                continue
            for test_id, outcome in report["outcomes"].items():
                if test_id in outcomes:
                    failures.append(f"duplicate shard result for {test_id}")
                outcomes[test_id] = outcome
                actual_ids.append(test_id)
        if len(actual_ids) != len(set(actual_ids)) or sorted(actual_ids) != sorted(parallel_ids):
            failures.append("Integration shard results do not cover exact parallel IDs")
    wall = time.perf_counter() - runner_started
    worker_seconds = sum(walls)
    return outcomes, failures, {
        "runner_wall_seconds": wall,
        "slowest_shard_seconds": max(walls, default=0.0),
        "worker_seconds": worker_seconds,
        "estimated_idle_worker_seconds": max(0.0, effective_jobs * wall - worker_seconds),
    }


def run_discovered_tests(cases: list[unittest.TestCase], jobs: int, verbosity: int = 2) -> int:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    inventory_ids = [case.id() for case in cases]
    parallel_ids, serial_ids = classify_test_inventory(cases)
    print(
        f"INTEGRATION_TEST_INVENTORY discovered={len(inventory_ids)} parallel={len(parallel_ids)} "
        f"serial_exclusive={len(serial_ids)} inventory_sha256={test_id_digest(inventory_ids)} "
        f"parallel_sha256={test_id_digest(parallel_ids)} serial_sha256={test_id_digest(serial_ids)}",
        flush=True,
    )
    schedulable_modules = {test_module_name(test_id) for test_id in parallel_ids}
    effective_jobs = min(jobs, len(schedulable_modules)) if jobs > 1 else 1
    if effective_jobs < 2:
        effective_jobs = 1
        mode = "serial-baseline" if jobs == 1 else "serial-fail-closed"
        print(f"INTEGRATION_WORKERS requested={jobs} effective=1 mode={mode}", flush=True)
        started = time.perf_counter()
        result = run_suite(cases, verbosity)
        wall = time.perf_counter() - started
        if set(result.outcomes) != set(inventory_ids):
            print("INTEGRATION_TEST_FAIL serial run omitted test IDs", file=sys.stderr)
            return 1
        counts = summarize_outcomes(result.outcomes)
        print(
            f"INTEGRATION_TEST_RESULT tests_run={len(result.outcomes)} passed={counts['passed']} "
            f"skipped={counts['skipped']} failures={counts['failures']} errors={counts['errors']} "
            f"outcome_sha256={outcome_digest(result.outcomes)}",
            flush=True,
        )
        print(f"INTEGRATION_WORKER_METRICS requested={jobs} effective=1 peak_workers=1 runner_wall_seconds={wall:.3f}", flush=True)
        return 0 if result.wasSuccessful() else 1

    shards = partition_test_ids(parallel_ids, effective_jobs)
    print(
        f"INTEGRATION_WORKERS requested={jobs} effective={effective_jobs} mode=deterministic-unittest-shards",
        flush=True,
    )
    print(
        f"INTEGRATION_SHARD_PLAN shards={','.join(str(len(shard)) for shard in shards)} "
        f"worker_modules={','.join(str(len(set(test_module_name(test_id) for test_id in shard))) for shard in shards)}",
        flush=True,
    )
    started = time.perf_counter()
    parallel_outcomes, failures, metrics = run_parallel_shards(inventory_ids, parallel_ids, effective_jobs, verbosity)
    serial_started = time.perf_counter()
    serial_cases = [case for case in cases if case.id() in set(serial_ids)]
    print(f"INTEGRATION_SERIAL_EXCLUSIVE_START tests={len(serial_cases)}", flush=True)
    serial_result = run_suite(serial_cases, verbosity)
    serial_seconds = time.perf_counter() - serial_started
    outcomes = dict(parallel_outcomes)
    for test_id, outcome in serial_result.outcomes.items():
        if test_id in outcomes:
            failures.append(f"serial test duplicated parallel result: {test_id}")
        outcomes[test_id] = outcome
    if len(outcomes) != len(inventory_ids) or set(outcomes) != set(inventory_ids):
        failures.append("Integration results do not cover exact discovered inventory")
    counts = summarize_outcomes(outcomes)
    runner_wall = time.perf_counter() - started
    print(
        f"INTEGRATION_TEST_RESULT tests_run={len(outcomes)} passed={counts['passed']} "
        f"skipped={counts['skipped']} failures={counts['failures']} errors={counts['errors']} "
        f"outcome_sha256={outcome_digest(outcomes)}",
        flush=True,
    )
    print(
        f"INTEGRATION_WORKER_METRICS requested={jobs} effective={effective_jobs} peak_workers={effective_jobs} "
        f"runner_wall_seconds={runner_wall:.3f} serial_seconds={serial_seconds:.3f} "
        f"slowest_shard_seconds={metrics['slowest_shard_seconds']:.3f} worker_seconds={metrics['worker_seconds']:.3f} "
        f"estimated_idle_worker_seconds={metrics['estimated_idle_worker_seconds']:.3f}",
        flush=True,
    )
    for failure in failures:
        print(f"INTEGRATION_TEST_FAIL {failure}", file=sys.stderr, flush=True)
    return 0 if serial_result.wasSuccessful() and not failures and counts["failures"] == 0 and counts["errors"] == 0 else 1


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1")
    return jobs


def sanitize_preflight_environment() -> None:
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        value = os.environ.pop(name, None)
        if value is None:
            continue
        if name == "PYTHONPATH":
            injected = {str(Path(item or os.curdir).resolve()) for item in value.split(os.pathsep)}
            sys.path[:] = [item for item in sys.path if str(Path(item or os.curdir).resolve()) not in injected]
        print(f"INTEGRATION_ENV_SANITIZED variable={name}", flush=True)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True


def run_fast(expected_head: str | None, jobs: int = 2) -> None:
    sanitize_preflight_environment()
    require_exact_head(expected_head)
    run([str(PYTHON), "-m", "compileall", "-q", "integration", "publication_bundle", "ci_artifacts", "scripts", "tests"])
    run(command("scripts/check_python_dependencies.py"))
    cases = discover_test_cases()
    validate_discovery(cases)
    if run_discovered_tests(cases, jobs, verbosity=2) != 0:
        raise PreflightFailure("Integration unittest discovery returned failures")


def validate_publication_lock() -> None:
    resolver = importlib.import_module("scripts.resolve_publication_sources")
    resolver.resolve_sources(ROOT / "publication-sources.json", {})


def validate_producer_identity(expected_head: str) -> None:
    resolver = importlib.import_module("scripts.resolve_producer_checkout")
    actual = resolver.resolve_checkout(ROOT)
    if actual != expected_head:
        raise PreflightFailure(f"producer identity mismatch: expected {expected_head}, found {actual}")


def fixture_round_trip() -> None:
    from ci_artifacts.publication_bundle import extract, pack
    from tests.test_publication_bundle import PROVIDERS, PRODUCER, finish, fixture

    with tempfile.TemporaryDirectory(prefix="integration-preflight-bundle-") as directory:
        root = Path(directory)
        bundle = fixture(root / "bundle")
        manifest = finish(bundle)
        archive = root / "bundle.tar"
        pack(bundle, archive)
        zip_path = root / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zipped:
            zipped.write(archive, "bundle.tar")
        digest = "sha256:" + hashlib.sha256(zip_path.read_bytes()).hexdigest()
        extracted = root / "extracted"
        actual = extract(
            zip_path,
            extracted,
            archive_digest=digest,
            identity=manifest["identity"],
            producer=PRODUCER["revision"],
            providers=PROVIDERS,
        )
        if actual != manifest:
            raise PreflightFailure("local Publication Bundle pack/extract round trip changed the manifest")


def run_ready(expected_head: str, jobs: int = 2) -> None:
    require_clean_tree()
    run_fast(expected_head, jobs)
    validate_publication_lock()
    validate_producer_identity(expected_head)
    fixture_round_trip()


def exact_revision(value: str, label: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise PreflightFailure(f"{label} must be a full lowercase commit SHA")
    return value


def require_clean_provider(root: Path, label: str, expected_revision: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise PreflightFailure(f"{label} checkout must be a regular directory")
    actual = git_output("rev-parse", "HEAD", cwd=root)
    if actual != expected_revision:
        raise PreflightFailure(f"{label} checkout does not match its exact revision")
    if git_output("status", "--porcelain=v1", "--untracked-files=all", cwd=root):
        raise PreflightFailure(f"{label} checkout must be clean before materialization")


def clone_provider_for_materialization(
    root: Path,
    revision: str,
    target: Path,
    label: str,
) -> Path:
    run(["git", "clone", "--quiet", "--shared", str(root), str(target)])
    run(["git", "-C", str(target), "checkout", "--quiet", "--detach", revision])
    require_clean_provider(target, label, revision)
    return target


def run_providers(args: argparse.Namespace, expected_head: str) -> None:
    composition_root = args.composition_root.resolve()
    policy_root = args.policy_root.resolve()
    composition_revision = exact_revision(args.composition_revision, "Composition revision")
    policy_revision = exact_revision(args.policy_revision, "Policy revision")
    modeling_root = args.modeling_root.resolve() if args.modeling_root else None
    modeling_revision = exact_revision(args.modeling_revision, "Modeling revision") if args.modeling_revision else None
    if (modeling_root is None) != (modeling_revision is None):
        raise PreflightFailure("Modeling root and revision must be supplied together")
    require_clean_tree()
    run_fast(expected_head, args.jobs)
    validate_publication_lock()
    validate_producer_identity(expected_head)
    resolve_producer = importlib.import_module("scripts.resolve_producer_checkout")
    if resolve_producer.resolve_checkout(composition_root) != composition_revision:
        raise PreflightFailure("Composition checkout does not match its exact revision")
    if resolve_producer.resolve_checkout(policy_root) != policy_revision:
        raise PreflightFailure("Policy checkout does not match its exact revision")
    if modeling_root is not None and resolve_producer.resolve_checkout(modeling_root) != modeling_revision:
        raise PreflightFailure("Modeling checkout does not match its exact revision")
    require_clean_provider(composition_root, "Composition", composition_revision)
    require_clean_provider(policy_root, "Policy", policy_revision)
    if modeling_root is not None:
        require_clean_provider(modeling_root, "Modeling", modeling_revision)
    with tempfile.TemporaryDirectory(prefix="integration-preflight-providers-") as directory:
        materialized_root = Path(directory) / "materialized-provider-inputs"
        materialized_root.mkdir()
        materialized_composition = clone_provider_for_materialization(
            composition_root,
            composition_revision,
            materialized_root / "composition",
            "Composition materialization",
        )
        materialized_policy = clone_provider_for_materialization(
            policy_root,
            policy_revision,
            materialized_root / "policy",
            "Policy materialization",
        )
        materialized_modeling = None
        if modeling_root is not None:
            materialized_modeling = clone_provider_for_materialization(
                modeling_root,
                modeling_revision,
                materialized_root / "modeling",
                "Modeling materialization",
            )
        materialization = [
            "scripts/materialize_publication_assets.py",
            "--publication", f"composition={materialized_composition}",
            "--publication", f"policy={materialized_policy}",
        ]
        if materialized_modeling is not None:
            materialization.extend(("--publication", f"modeling={materialized_modeling}"))
        run(command(*materialization))

        output = Path(directory) / "publication-bundle"
        qualification = [
            "scripts/qualify_integration.py",
            "--integration-root", str(ROOT),
            "--producer-revision", expected_head,
            "--composition-root", str(materialized_composition),
            "--composition-revision", composition_revision,
            "--policy-root", str(materialized_policy),
            "--policy-revision", policy_revision,
        ]
        if materialized_modeling is not None:
            qualification.extend(("--modeling-root", str(materialized_modeling), "--modeling-revision", modeling_revision))
        qualification.extend(("--output", str(output)))
        run(command(*qualification))
        archive = Path(directory) / "bundle.tar"
        run(command("scripts/publication_bundle_artifact.py", "pack", "--bundle", str(output), "--output", str(archive)))
        if not archive.is_file():
            raise PreflightFailure("provider qualification did not produce a Bundle archive")
        from ci_artifacts.publication_bundle import extract
        from publication_bundle.contract import validate

        manifest = validate(output)
        zip_path = Path(directory) / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zipped:
            zipped.write(archive, "bundle.tar")
        extracted = Path(directory) / "extracted"
        expected_providers = {"composition": composition_revision, "policy": policy_revision}
        if modeling_root is not None:
            expected_providers["modeling"] = modeling_revision
        extracted_manifest = extract(
            zip_path,
            extracted,
            archive_digest="sha256:" + hashlib.sha256(zip_path.read_bytes()).hexdigest(),
            identity=manifest["identity"],
            producer=expected_head,
            providers=expected_providers,
        )
        if extracted_manifest != manifest:
            raise PreflightFailure("provider Bundle pack/extract round trip changed the manifest")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("fast", "ready", "providers"))
    parser.add_argument("--jobs", type=positive_jobs, default=2, help="maximum Integration unittest workers (default: 2)")
    parser.add_argument("--worker-manifest", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--expected-head")
    parser.add_argument("--composition-root", type=Path)
    parser.add_argument("--composition-revision")
    parser.add_argument("--policy-root", type=Path)
    parser.add_argument("--policy-revision")
    parser.add_argument("--modeling-root", type=Path)
    parser.add_argument("--modeling-revision")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        sanitize_preflight_environment()
        if args.worker_manifest is not None:
            if args.profile != "fast" or args.jobs != 1:
                raise PreflightFailure("private shard workers require fast profile and --jobs 1")
            return run_shard_worker(args.worker_manifest)
        if args.profile == "fast":
            run_fast(args.expected_head, args.jobs)
        else:
            if not args.expected_head:
                raise PreflightFailure(f"{args.profile} requires --expected-head")
            expected_head = exact_revision(args.expected_head, "expected head")
            if args.profile == "ready":
                run_ready(expected_head, args.jobs)
            else:
                required = (
                    args.composition_root,
                    args.composition_revision,
                    args.policy_root,
                    args.policy_revision,
                )
                if any(value is None for value in required):
                    raise PreflightFailure("providers requires explicit Composition and Policy roots and revisions")
                run_providers(args, expected_head)
        print(f"INTEGRATION_PREFLIGHT_PASS profile={args.profile}", flush=True)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"INTEGRATION_PREFLIGHT_FAIL profile={args.profile}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
