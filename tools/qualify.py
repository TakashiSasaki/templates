#!/usr/bin/env python3
"""Canonical local/CI qualification: current projections and all discovered tests."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

# Isolated shard children intentionally ignore environment-provided Python paths.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from policy_distribution import check_policy_distribution  # noqa: E402

import catalog  # noqa: E402
import publication_export  # noqa: E402


PARALLEL_MODULE_MANIFEST = ROOT / "tools/qualification_parallel_test_modules.json"
# Set from exact-head jobs=1/2/4 measurements; requests above this remain bounded.
MEASURED_EFFECTIVE_WORKER_CAP = 4
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class QualificationError(RuntimeError):
    """The canonical qualification inventory or a worker result is invalid."""


def git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise QualificationError((result.stderr or result.stdout).strip() or "git command failed")
    return result.stdout.strip()


def qualification_head(root: Path, expected_head: str | None, *, require_clean: bool = False) -> str:
    if expected_head is not None and FULL_SHA.fullmatch(expected_head) is None:
        raise QualificationError("expected head must be a full lowercase commit SHA")
    actual_head = git_output(root, "rev-parse", "HEAD")
    if expected_head is not None and actual_head != expected_head:
        raise QualificationError(f"exact Modeling head mismatch: expected {expected_head}, found {actual_head}")
    if require_clean and git_output(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise QualificationError("exact-head qualification requires a clean index and working tree")
    print(
        f"MODELING_QUALIFICATION_HEAD actual={actual_head} "
        f"expected={expected_head or 'not-specified'} exact={expected_head is not None}",
        flush=True,
    )
    return actual_head


def check_progressive_discovery(root: Path) -> None:
    check_policy_distribution(root)
    script = root / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--format", "json"],
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"progressive discovery did not produce a report: {result.stderr}") from exc
    if result.returncode or report.get("result") != "NO_UPDATE_REQUIRED":
        raise ValueError(f"progressive discovery is not clean: {result.stdout}")


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


def discover_test_cases(root: Path) -> list[unittest.TestCase]:
    tests_dir = root / "tests"
    for path in (str(root), str(tests_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir), pattern="test_*.py")
    cases = flatten_suite(suite)
    failed_imports = [
        case.id()
        for case in cases
        if case.id().startswith("unittest.loader._FailedTest")
    ]
    if loader.errors or failed_imports:
        details = "; ".join(loader.errors + failed_imports)
        raise QualificationError(f"test discovery import failed: {details}")
    test_ids = [case.id() for case in cases]
    if len(set(test_ids)) != len(test_ids):
        raise QualificationError("test discovery returned duplicate test IDs")
    if not cases:
        raise QualificationError("No tests discovered; refusing empty qualification")
    files = sorted(tests_dir.glob("test_*.py"))
    discovered_modules = {case.__class__.__module__.rsplit(".", 1)[-1] for case in cases}
    missing = [path.stem for path in files if path.stem not in discovered_modules]
    if missing:
        raise QualificationError("test files missing from unittest discovery: " + ", ".join(missing))
    return cases


def load_parallel_module_manifest(root: Path) -> dict[str, dict[str, str]]:
    manifest_path = root / "tools/qualification_parallel_test_modules.json"
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise QualificationError(f"parallel test module manifest is unavailable: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "parallel_module_sha256"}:
        raise QualificationError("parallel test module manifest has unsupported fields")
    modules = value.get("parallel_module_sha256")
    if value.get("schema_version") != 1 or not isinstance(modules, dict):
        raise QualificationError("parallel test module manifest has an unsupported schema")
    for module, fingerprints in modules.items():
        if (
            not isinstance(module, str)
            or not module.startswith("test_")
            or not isinstance(fingerprints, dict)
            or set(fingerprints) != {"source_sha256", "test_ids_sha256"}
            or any(
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                for digest in fingerprints.values()
            )
        ):
            raise QualificationError("parallel test module manifest contains an invalid fingerprint")
    return modules


def classify_inventory(
    cases: list[unittest.TestCase], root: Path
) -> tuple[list[str], list[str]]:
    module_ids: dict[str, list[str]] = {}
    for case in cases:
        module = case.__class__.__module__.rsplit(".", 1)[-1]
        module_ids.setdefault(module, []).append(case.id())
    reviewed = load_parallel_module_manifest(root)
    parallel_modules = set()
    for module, ids in module_ids.items():
        expected = reviewed.get(module)
        source_path = root / "tests" / f"{module}.py"
        if expected is None or not source_path.is_file():
            continue
        if (
            hashlib.sha256(source_path.read_bytes()).hexdigest() == expected["source_sha256"]
            and test_id_digest(ids) == expected["test_ids_sha256"]
        ):
            parallel_modules.add(module)
    parallel = [
        case.id()
        for case in cases
        if case.__class__.__module__.rsplit(".", 1)[-1] in parallel_modules
    ]
    parallel_set = set(parallel)
    all_ids = [case.id() for case in cases]
    serial = [test_id for test_id in all_ids if test_id not in parallel_set]
    if parallel_set & set(serial) or parallel_set | set(serial) != set(all_ids):
        raise QualificationError("test inventory execution classes are incomplete or overlap")
    return parallel, serial


def partition_test_ids(test_ids: list[str] | tuple[str, ...], jobs: int) -> list[list[str]]:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    if len(set(test_ids)) != len(test_ids):
        raise ValueError("cannot shard duplicate test IDs")
    if not test_ids:
        return []
    worker_count = min(jobs, len(test_ids))
    shards: list[list[str]] = [[] for _ in range(worker_count)]
    stable_order = sorted(test_ids, key=lambda test_id: (hashlib.sha256(test_id.encode("utf-8")).digest(), test_id))
    for index, test_id in enumerate(stable_order):
        shards[index % worker_count].append(test_id)
    return shards


class InventoryTextTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: dict[str, dict[str, str]] = {}
        self._status_priority = {
            "passed": 0,
            "skipped": 1,
            "expected-failure": 2,
            "unexpected-success": 3,
            "failure": 4,
            "error": 5,
        }

    def _record(self, test: unittest.TestCase, status: str, reason: str | None = None) -> None:
        existing = self.outcomes.get(test.id())
        if existing is not None and self._status_priority[existing["status"]] >= self._status_priority[status]:
            return
        outcome = {"status": status}
        if reason is not None:
            outcome["reason"] = str(reason)
        self.outcomes[test.id()] = outcome

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
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
            status = "failure" if issubclass(err[0], test.failureException) else "error"
            self._record(test, status)


class InventoryTextTestRunner(unittest.TextTestRunner):
    resultclass = InventoryTextTestResult


def run_suite(cases: list[unittest.TestCase], verbosity: int = 2) -> InventoryTextTestResult:
    return InventoryTextTestRunner(verbosity=verbosity).run(unittest.TestSuite(cases))


def run_suite_without_worker_options(
    cases: list[unittest.TestCase], verbosity: int = 2
) -> InventoryTextTestResult:
    original_argv = sys.argv
    sys.argv = [original_argv[0]]
    try:
        return run_suite(cases, verbosity)
    finally:
        sys.argv = original_argv


def outcome_digest(outcomes: dict[str, dict[str, str]]) -> str:
    encoded = json.dumps(outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def outcome_counts(outcomes: dict[str, dict[str, str]]) -> dict[str, int]:
    counts = Counter(outcome["status"] for outcome in outcomes.values())
    return {
        "passed": counts["passed"],
        "skipped": counts["skipped"],
        "failures": counts["failure"],
        "errors": counts["error"],
        "expected_failures": counts["expected-failure"],
        "unexpected_successes": counts["unexpected-success"],
    }


def test_result_line(
    tests_run: int, counts: dict[str, int], outcomes: dict[str, dict[str, str]]
) -> str:
    return (
        f"MODELING_TEST_RESULT tests_run={tests_run} passed={counts['passed']} "
        f"skipped={counts['skipped']} failures={counts['failures']} errors={counts['errors']} "
        f"expected_failures={counts['expected_failures']} "
        f"unexpected_successes={counts['unexpected_successes']} "
        f"outcome_sha256={outcome_digest(outcomes)}"
    )


def load_tests_by_id(root: Path, test_ids: list[str]) -> list[unittest.TestCase]:
    for path in (str(root), str(root / "tests")):
        if path not in sys.path:
            sys.path.insert(0, path)
    loader = unittest.TestLoader()
    cases: list[unittest.TestCase] = []
    for test_id in test_ids:
        cases.extend(flatten_suite(loader.loadTestsFromName(test_id)))
    loaded_ids = [case.id() for case in cases]
    if len(loaded_ids) != len(set(loaded_ids)) or set(loaded_ids) != set(test_ids):
        raise QualificationError("worker imports differ from the exact assigned test IDs")
    return cases


def worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        if environment.pop(name, None) is not None:
            print(f"MODELING_ENV_SANITIZED variable={name}", flush=True)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_shard_worker(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "inventory_ids", "shard_ids", "shard_index", "shard_count", "result_path", "head_sha"
    }
    if not isinstance(manifest, dict) or set(manifest) != required or manifest["schema_version"] != 1:
        raise QualificationError("worker shard manifest is malformed")
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
        or not isinstance(manifest["shard_index"], int)
        or not isinstance(manifest["shard_count"], int)
        or not isinstance(manifest["head_sha"], str)
    ):
        raise QualificationError("worker shard manifest has an invalid inventory")
    if manifest["head_sha"] and qualification_head(ROOT, manifest["head_sha"]) != manifest["head_sha"]:
        raise QualificationError("worker source head differs from its parent qualification")
    cases = load_tests_by_id(ROOT, shard_ids)
    print(
        f"MODELING_SHARD_START shard={manifest['shard_index']}/{manifest['shard_count']} "
        f"tests={len(shard_ids)} ids_sha256={test_id_digest(shard_ids)}",
        flush=True,
    )
    result = run_suite_without_worker_options(cases)
    result_path = Path(manifest["result_path"])
    if result_path.parent.resolve() != manifest_path.parent.resolve():
        raise QualificationError("worker result must stay beside its private manifest")
    payload = {
        "shard_index": manifest["shard_index"],
        "ran_ids": sorted(result.outcomes),
        "outcomes": result.outcomes,
        "tests_run": result.testsRun,
        "outcome_sha256": outcome_digest(result.outcomes),
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if result.testsRun != len(shard_ids) or sorted(result.outcomes) != sorted(shard_ids):
        return 1
    return 0 if result.wasSuccessful() else 1


def run_parallel_shards(
    inventory_ids: list[str], parallel_ids: list[str], jobs: int, head_sha: str | None = None
) -> tuple[dict[str, dict[str, str]], list[str], dict[str, float]]:
    shards = partition_test_ids(parallel_ids, jobs)
    if not shards:
        return {}, [], {
            "runner_wall_seconds": 0.0,
            "slowest_shard_seconds": 0.0,
            "worker_seconds": 0.0,
            "estimated_idle_worker_seconds": 0.0,
        }
    effective_jobs = len(shards)
    wall_started = time.perf_counter()
    failures: list[str] = []
    reports: dict[int, tuple[int, float, str, str, dict[str, object] | None]] = {}
    with tempfile.TemporaryDirectory(prefix="modeling-qualification-shards-") as directory:
        private_root = Path(directory)
        manifests: dict[int, Path] = {}
        result_paths: dict[int, Path] = {}
        for index, shard_ids in enumerate(shards):
            manifest_path = private_root / f"shard-{index}-manifest.json"
            result_path = private_root / f"shard-{index}-result.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "inventory_ids": inventory_ids,
                        "shard_ids": shard_ids,
                        "shard_index": index,
                        "shard_count": effective_jobs,
                        "result_path": str(result_path),
                        "head_sha": head_sha or "",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifests[index] = manifest_path
            result_paths[index] = result_path

        def execute(index: int) -> tuple[int, float, str, str, dict[str, object] | None]:
            command = [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--jobs",
                "1",
                "--worker-manifest",
                str(manifests[index]),
            ]
            started = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=worker_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            elapsed = time.perf_counter() - started
            report = None
            if result_paths[index].is_file():
                try:
                    report = json.loads(result_paths[index].read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    return completed.returncode or 1, elapsed, completed.stdout, f"invalid worker report: {exc}", None
            return completed.returncode, elapsed, completed.stdout, completed.stderr, report

        with ThreadPoolExecutor(max_workers=effective_jobs, thread_name_prefix="modeling-test-shard") as executor:
            futures = {executor.submit(execute, index): index for index in range(effective_jobs)}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    reports[index] = future.result()
                except Exception as exc:
                    reports[index] = (1, 0.0, "", f"worker could not complete: {exc}", None)

        walls: list[float] = []
        outcomes: dict[str, dict[str, str]] = {}
        actual_ids: list[str] = []
        for index in range(effective_jobs):
            return_code, elapsed, stdout, stderr, report = reports[index]
            walls.append(elapsed)
            if stdout:
                print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
            if stderr:
                print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
            if return_code != 0:
                failures.append(f"shard {index}/{effective_jobs} exited with {return_code}")
            if not isinstance(report, dict) or report.get("ran_ids") != sorted(shards[index]):
                failures.append(f"shard {index}/{effective_jobs} omitted or duplicated assigned IDs")
                report = None
            print(
                f"MODELING_SHARD_RESULT shard={index}/{effective_jobs} "
                f"ids_sha256={test_id_digest(shards[index])} wall_seconds={elapsed:.3f} exit_code={return_code}",
                flush=True,
            )
            if not isinstance(report, dict) or not isinstance(report.get("outcomes"), dict):
                failures.append(f"shard {index}/{effective_jobs} returned malformed outcomes")
                continue
            for test_id, outcome in report["outcomes"].items():
                if test_id in outcomes:
                    failures.append(f"duplicate shard result for {test_id}")
                outcomes[test_id] = outcome
                actual_ids.append(test_id)

        assigned = [test_id for shard in shards for test_id in shard]
        if len(assigned) != len(set(assigned)) or sorted(assigned) != sorted(parallel_ids):
            failures.append("shard plan has missing or duplicate test IDs")
        if len(actual_ids) != len(set(actual_ids)) or sorted(actual_ids) != sorted(parallel_ids):
            failures.append("shard results do not cover exact parallel test IDs")
        wall = time.perf_counter() - wall_started
        worker_seconds = sum(walls)
    return outcomes, failures, {
        "runner_wall_seconds": wall,
        "slowest_shard_seconds": max(walls, default=0.0),
        "worker_seconds": worker_seconds,
        "estimated_idle_worker_seconds": max(0.0, effective_jobs * wall - worker_seconds),
    }


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1")
    return jobs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=positive_jobs, default=1, help="maximum Modeling unittest workers (default: 1)")
    parser.add_argument("--expected-head", help="require this exact clean Modeling commit SHA")
    parser.add_argument("--worker-manifest", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run_discovered_tests(
    cases: list[unittest.TestCase], jobs: int, root: Path, head_sha: str | None = None
) -> int:
    if jobs < 1:
        raise ValueError("jobs must be an integer of at least 1")
    inventory_ids = [case.id() for case in cases]
    parallel_ids, serial_ids = classify_inventory(cases, root)
    print(
        f"MODELING_TEST_INVENTORY discovered={len(inventory_ids)} parallel={len(parallel_ids)} "
        f"serial_exclusive={len(serial_ids)} inventory_sha256={test_id_digest(inventory_ids)} "
        f"parallel_sha256={test_id_digest(parallel_ids)} serial_sha256={test_id_digest(serial_ids)}",
        flush=True,
    )
    effective_jobs = min(jobs, MEASURED_EFFECTIVE_WORKER_CAP, len(parallel_ids)) if jobs > 1 else 1
    if effective_jobs < 2:
        print(f"MODELING_WORKERS requested={jobs} effective=1 mode=serial-baseline-or-measured-cap", flush=True)
        started = time.perf_counter()
        result = run_suite_without_worker_options(cases)
        elapsed = time.perf_counter() - started
        if set(result.outcomes) != set(inventory_ids) or len(result.outcomes) != len(inventory_ids):
            print("MODELING_QUALIFICATION_FAIL serial run omitted or duplicated test IDs", file=sys.stderr, flush=True)
            return 1
        counts = outcome_counts(result.outcomes)
        print(test_result_line(len(result.outcomes), counts, result.outcomes), flush=True)
        print(
            f"MODELING_WORKER_METRICS requested={jobs} effective=1 peak_workers=1 "
            f"runner_wall_seconds={elapsed:.3f}",
            flush=True,
        )
        return 0 if result.wasSuccessful() else 1

    shards = partition_test_ids(parallel_ids, effective_jobs)
    effective_jobs = len(shards)
    print(
        f"MODELING_WORKERS requested={jobs} effective={effective_jobs} mode=deterministic-test-id-shards "
        f"measured_cap={MEASURED_EFFECTIVE_WORKER_CAP}",
        flush=True,
    )
    print(
        f"MODELING_SHARD_PLAN shards={','.join(str(len(shard)) for shard in shards)}",
        flush=True,
    )
    started = time.perf_counter()
    parallel_outcomes, failures, metrics = run_parallel_shards(
        inventory_ids, parallel_ids, effective_jobs, head_sha
    )
    serial_started = time.perf_counter()
    serial_cases = [case for case in cases if case.id() in set(serial_ids)]
    print(f"MODELING_SERIAL_EXCLUSIVE_START tests={len(serial_cases)}", flush=True)
    serial_result = run_suite_without_worker_options(serial_cases)
    serial_seconds = time.perf_counter() - serial_started
    outcomes = dict(parallel_outcomes)
    for test_id, outcome in serial_result.outcomes.items():
        if test_id in outcomes:
            failures.append(f"serial test duplicated parallel result: {test_id}")
        outcomes[test_id] = outcome
    if len(outcomes) != len(inventory_ids) or set(outcomes) != set(inventory_ids):
        failures.append("results do not cover exact discovered test inventory")
    counts = outcome_counts(outcomes)
    runner_wall = time.perf_counter() - started
    print(test_result_line(len(outcomes), counts, outcomes), flush=True)
    print(
        f"MODELING_WORKER_METRICS requested={jobs} effective={effective_jobs} peak_workers={effective_jobs} "
        f"runner_wall_seconds={runner_wall:.3f} serial_seconds={serial_seconds:.3f} "
        f"slowest_shard_seconds={metrics['slowest_shard_seconds']:.3f} worker_seconds={metrics['worker_seconds']:.3f} "
        f"estimated_idle_worker_seconds={metrics['estimated_idle_worker_seconds']:.3f}",
        flush=True,
    )
    for failure in failures:
        print(f"MODELING_QUALIFICATION_FAIL {failure}", file=sys.stderr, flush=True)
    return 0 if (
        serial_result.wasSuccessful()
        and not failures
        and counts["failures"] == 0
        and counts["errors"] == 0
        and counts["unexpected_successes"] == 0
    ) else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.worker_manifest is not None:
        if args.jobs != 1:
            raise QualificationError("private shard workers require --jobs 1")
        if args.expected_head is not None:
            qualification_head(ROOT, args.expected_head)
        try:
            return run_shard_worker(args.worker_manifest)
        except (OSError, ValueError, QualificationError) as exc:
            print(f"Modeling shard failed: {exc}", file=sys.stderr)
            return 1
    root = Path(__file__).resolve().parents[1]
    try:
        head_sha = qualification_head(root, args.expected_head, require_clean=args.expected_head is not None)
    except QualificationError as exc:
        print(f"Modeling qualification failed: {exc}", file=sys.stderr)
        return 1
    try:
        records, collections = catalog.project(root, check=True)
        publication_export.validate(root)
        check_progressive_discovery(root)
    except (catalog.CatalogError, publication_export.ExportError, OSError, UnicodeError, ValueError) as exc:
        print(f"Catalog qualification failed: {exc}", file=sys.stderr)
        return 1
    try:
        cases = discover_test_cases(root)
        print(
            f"Qualifying {records} records, {collections} collections; {len(cases)} tests; "
            f"Python {sys.version.split()[0]}",
            flush=True,
        )
        return run_discovered_tests(cases, args.jobs, root, head_sha)
    except (OSError, ValueError, QualificationError) as exc:
        print(f"Modeling qualification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
