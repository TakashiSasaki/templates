#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON_ROOTS = (
    ROOT / "src",
    ROOT / "tests",
    ROOT / "scripts",
    ROOT / "repository-skills",
    ROOT / "skills" / "agent-policy" / "scripts",
)


ExecutionClass = Literal["parallel/process", "isolated-workspace", "exclusive"]
PARALLEL_EXECUTION_CLASSES = frozenset({"parallel/process", "isolated-workspace"})
DEFAULT_JOBS = 2


class FocusedTest(NamedTuple):
    path: str
    execution_class: ExecutionClass
    reason: str = ""


FOCUSED_TEST_SPECS: tuple[FocusedTest, ...] = (
    FocusedTest(
        "tests/test_config_driven_check.py",
        execution_class="isolated-workspace",
        reason="isolated tmp_path repo checks",
    ),
    FocusedTest(
        "tests/test_topology_contract_provenance.py",
        execution_class="parallel/process",
        reason="read-only snapshot provenance",
    ),
    FocusedTest(
        "tests/test_topology_change_orchestration.py",
        execution_class="parallel/process",
        reason="read-only topology specification and in-memory structures",
    ),
    FocusedTest(
        "tests/test_local_checkout_discovery.py",
        execution_class="isolated-workspace",
        reason="isolated tmp_path checkout discovery",
    ),
    FocusedTest(
        "tests/test_local_checkout_contract_provenance.py",
        execution_class="parallel/process",
        reason="read-only snapshot provenance",
    ),
    FocusedTest(
        "tests/test_qualification_sequencing.py",
        execution_class="isolated-workspace",
        reason="in-memory frontier sequencing and isolated tmp_path repin checks",
    ),
    FocusedTest(
        "tests/test_preflight_orchestration.py",
        execution_class="isolated-workspace",
        reason="mock authorities executed strictly inside tmp_path",
    ),
    FocusedTest(
        "tests/test_policy_fast_preflight_parallelism.py",
        execution_class="parallel/process",
        reason="in-memory mock registry and event synchronization",
    ),
    FocusedTest(
        "tests/test_policy_focused_tests_parallelism.py",
        execution_class="parallel/process",
        reason="in-memory command construction and classification invariant checks",
    ),
    FocusedTest(
        "tests/test_matched_policy_delivery.py",
        execution_class="isolated-workspace",
        reason=(
            "synthetic candidate repositories and experiments created strictly inside tmp_path"
        ),
    ),
    FocusedTest(
        "tests/test_policy_delivery_evidence_spec.py",
        execution_class="parallel/process",
        reason="exhaustive in-memory transition state-machine model checking",
    ),
    FocusedTest(
        "tests/test_policy_delivery_evidence_consistency.py",
        execution_class="parallel/process",
        reason="read-only smoke result verification and tmp_path tamper tests",
    ),
    FocusedTest(
        "tests/test_policy_applicability.py",
        execution_class="parallel/process",
        reason="isolated policy applicability model and scenario verification",
    ),
    FocusedTest(
        "tests/test_prospective_self_host_qualification_boundary.py",
        execution_class="parallel/process",
        reason="process-wide monkeypatching of package_root and repository self-host checks",
    ),
)

FOCUSED_TESTS: tuple[str, ...] = tuple(spec.path for spec in FOCUSED_TEST_SPECS)
PARALLEL_FOCUSED_TESTS: tuple[str, ...] = tuple(
    spec.path
    for spec in FOCUSED_TEST_SPECS
    if spec.execution_class in PARALLEL_EXECUTION_CLASSES
)
EXCLUSIVE_FOCUSED_TESTS: tuple[str, ...] = tuple(
    spec.path for spec in FOCUSED_TEST_SPECS if spec.execution_class == "exclusive"
)
FULL_PARALLEL_MANIFEST = ROOT / "tests" / "policy_parallel_test_manifest.json"


class TestPartition(NamedTuple):
    discovered: tuple[str, ...]
    parallel: tuple[str, ...]
    serial: tuple[str, ...]
    exclusive: tuple[str, ...]
    fallback_modules: tuple[str, ...]


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be an integer >= 1") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be >= 1")
    return jobs


def effective_focused_jobs(requested_jobs: int) -> int:
    if requested_jobs < 1:
        raise ValueError("jobs must be at least 1")
    return min(requested_jobs, max(1, len(PARALLEL_FOCUSED_TESTS)))


def effective_full_test_jobs(
    requested_jobs: int, *, schedulable_modules: int | None = None
) -> int:
    if requested_jobs < 1:
        raise ValueError("jobs must be at least 1")
    worker_cap = (
        len(PARALLEL_FOCUSED_TESTS)
        if schedulable_modules is None
        else schedulable_modules
    )
    return min(requested_jobs, max(1, worker_cap))


def effective_runner_jobs(
    profile: str,
    requested_jobs: int,
    checks: Sequence[str] | None = None,
    *,
    schedulable_modules: int | None = None,
) -> int:
    if checks:
        if "focused-tests" in checks:
            return effective_focused_jobs(requested_jobs)
        if "tests" in checks:
            return effective_full_test_jobs(
                requested_jobs, schedulable_modules=schedulable_modules
            )
        return 1
    if profile == "fast":
        return max(min(requested_jobs, 2), effective_focused_jobs(requested_jobs))
    if profile in {"full", "ready"}:
        return effective_full_test_jobs(
            requested_jobs, schedulable_modules=schedulable_modules
        )
    return 1


def _node_ids_digest(node_ids: Sequence[str]) -> str:
    payload = json.dumps(
        sorted(node_ids), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def classify_full_test_inventory(
    node_ids: Sequence[str],
    root: Path = ROOT,
    manifest_path: Path = FULL_PARALLEL_MANIFEST,
) -> TestPartition:
    """Fail closed: only fingerprinted focused modules enter the parallel lane."""

    discovered = tuple(node_ids)
    if len(set(discovered)) != len(discovered):
        raise ValueError("pytest discovery returned duplicate test node IDs")
    if not discovered:
        raise ValueError("pytest discovery returned an empty test inventory")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("modules"), dict):
        raise ValueError("invalid Policy parallel test manifest")

    specs = {spec.path: spec for spec in FOCUSED_TEST_SPECS}
    module_ids: dict[str, list[str]] = {}
    for node_id in discovered:
        module = node_id.split("::", 1)[0]
        module_ids.setdefault(module, []).append(node_id)

    parallel: list[str] = []
    serial: list[str] = []
    exclusive: list[str] = []
    fallback_modules: list[str] = []
    for module, ids in module_ids.items():
        spec = specs.get(module)
        if spec is not None and spec.execution_class == "exclusive":
            exclusive.extend(ids)
            continue
        if spec is None or spec.execution_class not in PARALLEL_EXECUTION_CLASSES:
            serial.extend(ids)
            continue

        expected = manifest["modules"].get(module)
        source = root / module
        source_digest = (
            hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
        )
        current = {
            "count": len(ids),
            "node_ids_sha256": _node_ids_digest(ids),
            "source_sha256": source_digest,
        }
        if expected == current:
            parallel.extend(ids)
        else:
            # Added, removed, renamed, or edited tests require a new safety
            # review before their module can re-enter the parallel lane.
            serial.extend(ids)
            fallback_modules.append(module)

    partition = TestPartition(
        discovered=discovered,
        parallel=tuple(sorted(parallel)),
        serial=tuple(sorted(serial)),
        exclusive=tuple(sorted(exclusive)),
        fallback_modules=tuple(sorted(fallback_modules)),
    )
    parallel_set = set(partition.parallel)
    serial_set = set(partition.serial)
    exclusive_set = set(partition.exclusive)
    discovered_set = set(discovered)
    if (parallel_set & serial_set) or (parallel_set & exclusive_set) or (
        serial_set & exclusive_set
    ):
        raise ValueError("Policy pytest execution classes overlap")
    if parallel_set | serial_set | exclusive_set != discovered_set:
        raise ValueError("Policy pytest execution classes do not cover discovery")
    return partition


def collect_full_test_inventory() -> tuple[str, ...]:
    with tempfile.TemporaryDirectory(prefix="policy-pytest-inventory-") as directory:
        inventory_file = Path(directory) / "node-ids.json"
        run(
            sys.executable,
            "scripts/collect_policy_test_inventory.py",
            "--output",
            inventory_file,
        )
        node_ids = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(node_ids, list) or any(not isinstance(item, str) for item in node_ids):
        raise ValueError("Policy pytest collector returned malformed node IDs")
    return tuple(node_ids)


def schedulable_full_test_module_count() -> int:
    """Return the module cap from the current exact discovered inventory."""

    partition = classify_full_test_inventory(collect_full_test_inventory())
    return len({node_id.split("::", maxsplit=1)[0] for node_id in partition.parallel})


def run_pytest_subset(
    name: str, node_ids: Sequence[str], requested_jobs: int, effective_jobs: int
) -> None:
    if not node_ids:
        return
    selection_hash = _node_ids_digest(node_ids)
    worker_args = (
        ("-n", str(effective_jobs), "--dist=loadfile")
        if name == "parallel" and effective_jobs > 1
        else ()
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=-q",
        "--durations=0",
        "--durations-min=0",
        *worker_args,
        *node_ids,
    ]
    print(
        f"POLICY_TEST_PHASE name={name} requested={requested_jobs} "
        f"effective={effective_jobs if name == 'parallel' else 1} "
        f"tests={len(node_ids)} node_ids_sha256={selection_hash}",
        flush=True,
    )
    subprocess.run(command, cwd=ROOT, env=sanitized_environment(), check=True)


def sanitized_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIP_")
        and not key.startswith("PYTHON")
        and not key.startswith("PYTEST_")
    }
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PYTHONNOUSERSITE"] = "1"
    # The preflight must execute the package from the exact worktree under
    # test.  Without this explicit path, a shared editable install can point
    # ``python -m agent_policy`` at another worktree and produce a false
    # self-check result.
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    return environment


def run(*arguments: str) -> None:
    command = [str(argument) for argument in arguments]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=sanitized_environment(), check=True)


def exact_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def foreign_snapshot_python_paths(root: Path = ROOT) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for manifest_path in sorted((root / "src" / "agent_policy").glob("_*_contract/source.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("authority") == "policy":
            continue
        bundle = manifest_path.parent
        for entry in manifest.get("files", []):
            destination = entry.get("destination")
            if not isinstance(destination, str):
                raise ValueError(f"invalid snapshot destination in {manifest_path}")
            candidate = (bundle / destination).resolve()
            try:
                candidate.relative_to(bundle.resolve())
            except ValueError as exc:
                raise ValueError(
                    f"snapshot destination escapes its bundle: {destination}"
                ) from exc
            if candidate.suffix == ".py":
                if not candidate.is_file():
                    raise ValueError(f"missing immutable snapshot: {candidate}")
                paths.add(candidate)
    return tuple(sorted(paths))


def policy_owned_python_paths(root: Path = ROOT) -> tuple[Path, ...]:
    foreign = set(foreign_snapshot_python_paths(root))
    roots = (
        root / "src",
        root / "tests",
        root / "scripts",
        root / "repository-skills",
        root / "skills" / "agent-policy" / "scripts",
    )
    return tuple(
        sorted(
            path
            for directory in roots
            for path in directory.rglob("*.py")
            if path.resolve() not in foreign
        )
    )


def check_compile() -> None:
    run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "src",
        "scripts",
        "repository-skills",
        "skills/agent-policy/scripts",
    )


def check_environment() -> None:
    run(sys.executable, "scripts/verify_ci_environment.py")
    run(sys.executable, "-m", "pip", "check")


def check_installer() -> None:
    source_ref = os.environ.get("POLICY_SOURCE_REF", "HEAD")
    run(
        sys.executable,
        "scripts/verify_skill_installer_release.py",
        "--git-ref",
        source_ref,
    )


def check_translations() -> None:
    run(sys.executable, "scripts/validate_translations.py", "--allow-stale")


def check_lint() -> None:
    paths = [path.relative_to(ROOT).as_posix() for path in policy_owned_python_paths()]
    if not paths:
        raise RuntimeError("no Policy-owned Python files were discovered")
    run(sys.executable, "-m", "ruff", "--version")
    run(sys.executable, "-m", "ruff", "check", *paths)


def check_focused_tests(jobs: int = DEFAULT_JOBS) -> None:
    missing = [path for path in FOCUSED_TESTS if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"focused Policy test suites are missing: {', '.join(missing)}")
    effective_jobs = effective_focused_jobs(jobs)
    print(
        "POLICY_TEST_WORKERS suite=focused "
        f"requested={jobs} effective={effective_jobs} "
        f"parallel_tests={len(PARALLEL_FOCUSED_TESTS)} "
        f"exclusive_tests={len(EXCLUSIVE_FOCUSED_TESTS)}",
        flush=True,
    )
    pytest_args = ("-o", "addopts=-q")
    if PARALLEL_FOCUSED_TESTS:
        worker_args = (
            ("-n", str(effective_jobs), "--dist=loadfile")
            if effective_jobs > 1
            else ()
        )
        run(
            sys.executable,
            "-m",
            "pytest",
            *pytest_args,
            *worker_args,
            *PARALLEL_FOCUSED_TESTS,
        )
    if EXCLUSIVE_FOCUSED_TESTS:
        run(
            sys.executable,
            "-m",
            "pytest",
            *pytest_args,
            *EXCLUSIVE_FOCUSED_TESTS,
        )
    run(sys.executable, "scripts/check_policy_delivery_evidence.py")


def check_tests(jobs: int = DEFAULT_JOBS) -> None:
    partition = classify_full_test_inventory(collect_full_test_inventory())
    parallel_modules = {
        node_id.split("::", maxsplit=1)[0] for node_id in partition.parallel
    }
    effective_jobs = effective_full_test_jobs(
        jobs, schedulable_modules=len(parallel_modules)
    )
    print(
        "POLICY_TEST_INVENTORY "
        f"discovered={len(partition.discovered)} parallel={len(partition.parallel)} "
        f"serial={len(partition.serial)} exclusive={len(partition.exclusive)} "
        f"inventory_sha256={_node_ids_digest(partition.discovered)}",
        flush=True,
    )
    for module in partition.fallback_modules:
        print(
            f"POLICY_TEST_CLASSIFICATION_FALLBACK module={module} lane=serial "
            "reason=parallel-safety-fingerprint-changed",
            flush=True,
        )
    print(
        f"POLICY_TEST_WORKERS suite=full requested={jobs} effective={effective_jobs}",
        flush=True,
    )
    if jobs == 1:
        run(
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=-q",
            "--durations=0",
            "--durations-min=0",
        )
        return
    run_pytest_subset("parallel", partition.parallel, jobs, effective_jobs)
    run_pytest_subset("serial", partition.serial, jobs, effective_jobs)
    run_pytest_subset("exclusive", partition.exclusive, jobs, effective_jobs)


def execute_check(
    registry: Mapping[str, Callable[..., None]], name: str, jobs: int
) -> None:
    check = registry[name]
    if name in {"focused-tests", "tests"}:
        check(jobs)
    else:
        check()


def check_candidate_qualification() -> None:
    run(sys.executable, "scripts/verify_candidate_qualification.py")


def check_self_host() -> None:
    run(sys.executable, "scripts/verify_policy_self_host.py")


def check_self() -> None:
    check_candidate_qualification()


def check_installed_command() -> None:
    executable = Path(sys.executable).with_name(
        "agent-policy.exe" if os.name == "nt" else "agent-policy"
    )
    run(str(executable), "--help")


def check_runtime() -> None:
    run(sys.executable, "-I", "scripts/smoke_test_runtime_distribution.py")


def check_docs() -> None:
    if os.environ.get("POLICY_DOCS_ENV_READY") != "1":
        run(sys.executable, "-I", "scripts/smoke_test_policy_documentation.py")
        return
    protocol = ROOT / "scripts/publication_catalog.py"
    run(sys.executable, "scripts/verify_docs_environment.py")
    run(sys.executable, "-m", "pip", "check")
    run(
        sys.executable,
        "-I",
        str(protocol),
        "--source-root",
        ".",
        "--catalog",
        "docs/publication-catalog.json",
    )
    run(sys.executable, "scripts/generate_repository_preview.py")
    run(sys.executable, "scripts/verify-repository-structure.py", "--check")
    check_translations()
    run(sys.executable, "scripts/generate-doc-assets.py")
    run(
        sys.executable,
        "scripts/generate_docs_build_info.py",
        "--commit",
        os.environ.get("BUILD_COMMIT", exact_head()),
        "--repository",
        os.environ.get("BUILD_REPOSITORY", "TakashiSasaki/templates"),
        "--run-id",
        os.environ.get("BUILD_RUN_ID", "0"),
        "--run-number",
        os.environ.get("BUILD_RUN_NUMBER", "0"),
    )
    run(sys.executable, "-m", "mkdocs", "build", "--strict", "--clean")


def check_dependency_boundary() -> None:
    run(sys.executable, "scripts/check_python_dependencies.py")


def check_release_state() -> None:
    source_ref = os.environ.get("POLICY_SOURCE_REF", "HEAD")
    run(sys.executable, "scripts/verify-release-state.py", "--git-ref", source_ref)


def check_trusted_review() -> None:
    source_ref = os.environ.get("POLICY_SOURCE_REF", "HEAD")
    run(
        sys.executable,
        "scripts/verify_trusted_review_candidate.py",
        "--git-ref",
        source_ref,
    )


def require_clean_tree() -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    ).strip()
    if status:
        raise RuntimeError(
            "ready requires a clean index and working tree with no untracked files"
        )


def fail_closed_decision(reason: str):
    from scripts.classify_policy_ci import Decision

    return Decision(True, reason, True, reason, "full")


def classify_ready_applicability(base_ref: str, head: str):
    """Reuse the CI classifier and make every classifier failure run both probes."""

    try:
        from scripts import classify_policy_ci

        paths = classify_policy_ci.changed_paths(base_ref, head)
        decision = classify_policy_ci.classify_paths(paths)
        if not isinstance(decision, classify_policy_ci.Decision):
            return fail_closed_decision("malformed-classifier-output")
        if not all(
            isinstance(value, bool)
            for value in (
                decision.release_state_required,
                decision.trusted_review_required,
            )
        ):
            return fail_closed_decision("unknown-applicability-result")
        return decision
    except Exception as exc:  # classifier uncertainty must never skip a probe
        print(f"Policy applicability classification fell back to full: {exc}", file=sys.stderr)
        return fail_closed_decision("base-classifier-unavailable")


def run_ready(
    base_ref: str, head: str, jobs: int = DEFAULT_JOBS
) -> tuple[str, ...]:
    require_clean_tree()
    selected = list(PROFILES["full"])
    decision = classify_ready_applicability(base_ref, head)
    if decision.release_state_required:
        selected.append("release-state")
    if decision.trusted_review_required:
        selected.append("trusted-review")
    for name in selected:
        print(f"POLICY_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
        execute_check(CHECKS, name, jobs)
        print(f"POLICY_PREFLIGHT_CHECK_PASS name={name} head={head}", flush=True)
    return tuple(selected)


CHECKS: dict[str, Callable[[], None]] = {
    "compile": check_compile,
    "environment": check_environment,
    "installer": check_installer,
    "translations": check_translations,
    "lint": check_lint,
    "focused-tests": check_focused_tests,
    "tests": check_tests,
    "candidate-qualification": check_candidate_qualification,
    "self-host": check_self_host,
    "self-check": check_self,
    "installed-command": check_installed_command,
    "runtime": check_runtime,
    "docs": check_docs,
    "dependency-boundary": check_dependency_boundary,
    "release-state": check_release_state,
    "trusted-review": check_trusted_review,
}

PROFILES = {
    "fast": ("compile", "lint", "focused-tests", "self-check"),
    "full": (
        "compile",
        "environment",
        "installer",
        "translations",
        "lint",
        "tests",
        "self-check",
        "installed-command",
        "runtime",
        "docs",
        "dependency-boundary",
    ),
}
PROFILES["ready"] = PROFILES["full"]


def run_fast(
    head: str,
    checks: Mapping[str, Callable[..., None]] | None = None,
    jobs: int = DEFAULT_JOBS,
) -> tuple[str, ...]:
    registry = CHECKS if checks is None else checks
    selected = PROFILES["fast"]

    # Stage 1: compile
    print(f"POLICY_PREFLIGHT_CHECK_START name=compile head={head}", flush=True)
    registry["compile"]()
    print(f"POLICY_PREFLIGHT_CHECK_PASS name=compile head={head}", flush=True)

    # Stage 2: parallel lint and self-check
    parallel_checks = ("lint", "self-check")
    for name in parallel_checks:
        print(f"POLICY_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)

    errors: list[tuple[str, BaseException]] = []
    errors_lock = threading.Lock()

    def _execute(check_name: str) -> None:
        try:
            registry[check_name]()
            print(f"POLICY_PREFLIGHT_CHECK_PASS name={check_name} head={head}", flush=True)
        except BaseException as exc:
            with errors_lock:
                errors.append((check_name, exc))

    check_workers = min(jobs, len(parallel_checks))
    if check_workers == 1:
        for name in parallel_checks:
            _execute(name)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=check_workers) as executor:
            futures = [executor.submit(_execute, name) for name in parallel_checks]
            concurrent.futures.wait(futures)

    if errors:
        if len(errors) == 1:
            first_name, first_exc = errors[0]
            if isinstance(
                first_exc,
                (OSError, RuntimeError, ValueError, subprocess.CalledProcessError),
            ):
                raise first_exc
            raise RuntimeError(f"{first_name} failed: {first_exc}") from first_exc
        descriptions = "; ".join(
            f"{name} ({exc})" for name, exc in sorted(errors, key=lambda item: item[0])
        )
        raise RuntimeError(f"parallel preflight checks failed: {descriptions}")

    # Stage 3: exclusive focused-tests
    print(f"POLICY_PREFLIGHT_CHECK_START name=focused-tests head={head}", flush=True)
    execute_check(registry, "focused-tests", jobs)
    print(f"POLICY_PREFLIGHT_CHECK_PASS name=focused-tests head={head}", flush=True)

    return selected


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run canonical Policy validation.")
    parser.add_argument("profile", nargs="?", choices=sorted(PROFILES), default="fast")
    parser.add_argument("--check", choices=sorted(CHECKS), action="append", dest="checks")
    parser.add_argument("--expected-head")
    parser.add_argument("--base-ref")
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        default=DEFAULT_JOBS,
        metavar="N",
        help="maximum Policy preflight workers (default: 2; use 1 for serial baseline)",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    head = exact_head()
    if args.expected_head and head != args.expected_head:
        print(
            f"POLICY_PREFLIGHT_FAIL head={head} expected={args.expected_head} "
            "reason=head-mismatch",
            file=sys.stderr,
        )
        return 1
    try:
        selected_checks = tuple(args.checks or PROFILES[args.profile])
        needs_full_inventory = "tests" in selected_checks
        schedulable_modules = (
            schedulable_full_test_module_count() if needs_full_inventory else None
        )
        effective_jobs = effective_runner_jobs(
            args.profile,
            args.jobs,
            args.checks,
            schedulable_modules=schedulable_modules,
        )
        print(
            f"POLICY_PREFLIGHT_WORKERS profile={args.profile} "
            f"requested={args.jobs} effective={effective_jobs}",
            flush=True,
        )
        if args.profile == "ready":
            if not args.expected_head:
                raise RuntimeError("ready requires --expected-head")
            if args.checks:
                raise RuntimeError(
                    "ready does not accept --check; use --base-ref for applicability"
                )
            if not args.base_ref:
                raise RuntimeError("ready requires --base-ref")
            selected = run_ready(args.base_ref, head, jobs=args.jobs)
        elif args.profile == "fast" and not args.checks:
            selected = run_fast(head, jobs=args.jobs)
        else:
            selected = selected_checks
            for name in selected:
                print(f"POLICY_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
                execute_check(CHECKS, name, args.jobs)
                print(f"POLICY_PREFLIGHT_CHECK_PASS name={name} head={head}", flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(
            f"POLICY_PREFLIGHT_FAIL profile={args.profile} head={head} error={exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"POLICY_PREFLIGHT_PASS profile={args.profile} head={head} "
        f"checks={','.join(selected)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
