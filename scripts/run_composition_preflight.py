#!/usr/bin/env python3
"""Run the canonical local and CI preflight for the Composition authority."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from run_unittest_shard import (  # noqa: E402
    discover_tests,
    digest_test_ids,
    select_tests_for_suite,
    shard_tests,
    validate_two_shard_timing_overrides,
)


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
DEFAULT_JOBS = 2
MAX_CORE_SHARDS = 2
TIMING_LOG_PREFIX = "COMPOSITION_UNITTEST_TIMING "
FOCUSED_TESTS = (
    "tests/test_maintainer_entrypoint.py",
    "tests/test_composition_schemas.py",
    "tests/test_topology_role.py",
    "tests/test_workspace_role.py",
    "tests/test_bare_worktree_contract.py",
)
RUNTIME_SMOKES = (
    "scripts/smoke_test_runtime_distribution.py",
    "scripts/smoke_test_materialized_validation.py",
    "scripts/smoke_test_skill_runner.py",
    "scripts/smoke_test_remote_skill_installer.py",
)
PUBLICATION_DESCRIPTOR = ROOT / "generated" / "publication-descriptor.json"
BYTECODE_ROOTS = tuple(
    ROOT / relative
    for relative in (
        "components",
        "catalog",
        "recipes",
        "schemas",
        "scripts",
        "tests",
        "skills/composition/scripts",
    )
)


class PreflightFailure(RuntimeError):
    """A named preflight check failed."""


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be an integer >= 1") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be an integer >= 1")
    return jobs


def effective_core_jobs(requested_jobs: int) -> int:
    if requested_jobs < 1:
        raise ValueError("requested jobs must be at least 1")
    return min(requested_jobs, MAX_CORE_SHARDS)


def command(*args: str) -> list[str]:
    return [str(PYTHON), "-B", *args]


def configure_validation_environment() -> None:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def run_check(name: str, argv: Sequence[str], *, env: dict[str, str] | None = None) -> None:
    print(f"COMPOSITION_PREFLIGHT_CHECK_START name={name}", flush=True)
    result = subprocess.run(argv, cwd=ROOT, env=env, check=False)
    if result.returncode != 0:
        raise PreflightFailure(f"{name} failed with exit code {result.returncode}")
    print(f"COMPOSITION_PREFLIGHT_CHECK_PASS name={name}", flush=True)


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise PreflightFailure(
            f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise PreflightFailure(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def copy_untracked_files(destination: Path) -> None:
    raw_paths = git_bytes("ls-files", "--others", "--exclude-standard", "-z")
    for raw_path in raw_paths.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            resolved = source.resolve(strict=False)
            try:
                destination_target = destination / resolved.relative_to(ROOT.resolve())
            except ValueError as exc:
                raise PreflightFailure(
                    f"untracked symlink escapes the Composition worktree: {relative}"
                ) from exc
            target.symlink_to(os.path.relpath(destination_target, target.parent))
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise PreflightFailure(
                f"cannot copy unsupported untracked input into shard workspace: {relative}"
            )


def validate_shard_workspace_symlinks(destination: Path) -> None:
    workspace_root = destination.resolve()
    for directory, child_directories, files in os.walk(destination, followlinks=False):
        for name in [*child_directories, *files]:
            path = Path(directory) / name
            if not path.is_symlink():
                continue
            try:
                path.resolve(strict=False).relative_to(workspace_root)
            except ValueError as exc:
                raise PreflightFailure(
                    f"isolated shard workspace contains an external symlink: {path}"
                ) from exc


def copy_working_tree_changes(destination: Path) -> None:
    staged = git_bytes("diff", "--cached", "--binary", "HEAD")
    if staged:
        result = subprocess.run(
            ["git", "-C", str(destination), "apply", "--binary", "--index", "-"],
            input=staged,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise PreflightFailure(
                "cannot apply staged changes to isolated shard workspace: "
                + result.stderr.decode("utf-8", errors="replace").strip()
            )
    unstaged = git_bytes("diff", "--binary")
    if unstaged:
        result = subprocess.run(
            ["git", "-C", str(destination), "apply", "--binary", "-"],
            input=unstaged,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise PreflightFailure(
                "cannot apply unstaged changes to isolated shard workspace: "
                + result.stderr.decode("utf-8", errors="replace").strip()
            )
    validate_shard_workspace_symlinks(destination)
    copy_untracked_files(destination)
    validate_shard_workspace_symlinks(destination)


def add_shard_worktrees(shard_count: int, parent: Path) -> list[Path]:
    worktrees: list[Path] = []
    try:
        for shard_index in range(shard_count):
            worktree = parent / f"shard-{shard_index}"
            result = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(worktree), "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise PreflightFailure(
                    f"cannot create isolated shard worktree {shard_index}: "
                    f"{(result.stderr or result.stdout).strip()}"
                )
            worktrees.append(worktree)
            copy_working_tree_changes(worktree)
        return worktrees
    except BaseException:
        remove_shard_worktrees(worktrees)
        raise


def remove_shard_worktrees(worktrees: Sequence[Path]) -> None:
    failures: list[str] = []
    for worktree in reversed(worktrees):
        result = subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(worktree)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            failures.append((result.stderr or result.stdout).strip())
    if failures:
        raise PreflightFailure(
            "cannot remove isolated shard worktree(s): " + "; ".join(failures)
        )


def run_one_core_shard(
    worktree: Path, shard_index: int, shard_count: int
) -> tuple[int, str, str, float]:
    started = time.perf_counter()
    result = subprocess.run(
        [
            str(PYTHON),
            "-B",
            "scripts/run_unittest_shard.py",
            "--suite",
            "core",
            "--shard-count",
            str(shard_count),
            "--shard-index",
            str(shard_index),
        ],
        cwd=worktree,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr, time.perf_counter() - started


def measured_shard_test_seconds(
    stdout: str,
    expected_test_ids: Sequence[str],
    *,
    shard_count: int,
    shard_index: int,
) -> float:
    expected = set(expected_test_ids)
    observed: dict[str, float] = {}
    for line in stdout.splitlines():
        if not line.startswith(TIMING_LOG_PREFIX):
            continue
        try:
            record = json.loads(line.removeprefix(TIMING_LOG_PREFIX))
            if not isinstance(record, dict):
                raise TypeError("timing payload must be a JSON object")
            if (
                record.get("suite") != "core"
                or record.get("shard_count") != shard_count
                or record.get("shard_index") != shard_index
            ):
                continue
            test_id = record["test_id"]
            if not isinstance(test_id, str):
                raise TypeError("test_id must be a string")
            duration = float(record["duration_seconds"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PreflightFailure(
                f"invalid Composition timing record for shard {shard_index}/{shard_count}"
            ) from exc
        if test_id not in expected:
            # Test cases can exercise the preflight and print nested timing logs.
            # The final shard result record independently verifies the exact ID set.
            continue
        if test_id in observed:
            raise PreflightFailure(
                f"duplicate timed test ID in shard {shard_index}/{shard_count}: {test_id}"
            )
        if duration < 0 or not math.isfinite(duration):
            raise PreflightFailure(
                f"invalid duration for shard {shard_index}/{shard_count}: {test_id}"
            )
        observed[test_id] = duration

    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        raise PreflightFailure(
            f"Composition shard {shard_index}/{shard_count} timing inventory is incomplete: "
            + ", ".join(missing[:5])
        )
    return sum(observed.values())


def run_core_test_shards(requested_jobs: int) -> None:
    started = time.perf_counter()
    effective = effective_core_jobs(requested_jobs)
    print(
        f"COMPOSITION_WORKERS requested={requested_jobs} effective={effective} "
        "runner=composition-core mode=deterministic-unittest-shards",
        flush=True,
    )
    if effective == 1:
        serial_started = time.perf_counter()
        run_check(
            "core-tests",
            command(
                "scripts/run_unittest_shard.py",
                "--suite",
                "core",
                "--shard-count",
                "1",
                "--shard-index",
                "0",
            ),
        )
        serial_wall = time.perf_counter() - serial_started
        print(
            "COMPOSITION_WORKER_METRICS "
            f"requested={requested_jobs} effective=1 peak_shard_workers=1 "
            f"runner_wall_seconds={serial_wall:.3f} "
            f"slowest_shard_seconds={serial_wall:.3f} "
            f"shard_worker_seconds={serial_wall:.3f} estimated_idle_worker_seconds=0.000",
            flush=True,
        )
        return

    discovered = discover_tests(ROOT / "tests", "test*.py")
    validate_two_shard_timing_overrides(discovered)
    selected = select_tests_for_suite(discovered, "core")
    ids = [test.id() for test in selected]
    if len(ids) != len(set(ids)):
        raise PreflightFailure("Composition core unittest discovery contains duplicate test IDs")
    shards = shard_tests(selected, effective)
    flattened_ids = [test.id() for shard in shards for test in shard]
    if len(flattened_ids) != len(ids) or set(flattened_ids) != set(ids):
        raise PreflightFailure("Composition deterministic shard inventory is incomplete")
    shard_digests = [
        digest_test_ids([test.id() for test in shard]) for shard in shards
    ]
    inventory_digest = digest_test_ids(ids)
    print(
        "COMPOSITION_SHARD_PLAN "
        f"suite=core inventory={len(ids)} inventory_sha256={inventory_digest} "
        f"requested={requested_jobs} effective={effective} "
        f"shards={','.join(str(len(shard)) for shard in shards)}",
        flush=True,
    )

    with tempfile.TemporaryDirectory(prefix="composition-core-shards-") as temporary:
        parent = Path(temporary)
        worktrees = add_shard_worktrees(effective, parent)
        results: list[tuple[int, str, str, float] | None] = [None] * effective
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=effective) as executor:
                future_map = {
                    executor.submit(run_one_core_shard, worktree, index, effective): index
                    for index, worktree in enumerate(worktrees)
                }
                for future in concurrent.futures.as_completed(future_map):
                    index = future_map[future]
                    results[index] = future.result()
        finally:
            remove_shard_worktrees(worktrees)

    failed = False
    shard_durations: list[float] = []
    estimated_test_seconds: list[float] = []
    for index, result in enumerate(results):
        if result is None:
            failed = True
            print(
                f"COMPOSITION_SHARD_FAIL shard={index}/{effective} missing-result",
                flush=True,
            )
            continue
        returncode, stdout, stderr, duration = result
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
        observed_digest = None
        observed_run_count = None
        observed_run_digest = None
        for line in stdout.splitlines():
            if (
                observed_digest is None
                and line.startswith("COMPOSITION_UNITTEST_INVENTORY ")
            ):
                fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
                observed_digest = fields.get("selected_ids_sha256")
            elif line.startswith("COMPOSITION_UNITTEST_SHARD_RESULT "):
                fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
                observed_run_count = fields.get("run_count")
                observed_run_digest = fields.get("run_ids_sha256")
        expected_shard_digest = shard_digests[index]
        if observed_digest != inventory_digest:
            failed = True
            print(
                f"COMPOSITION_SHARD_FAIL shard={index}/{effective} "
                f"inventory_sha256={observed_digest} expected={inventory_digest}",
                flush=True,
            )
        expected_count = len(shards[index])
        if (
            observed_run_count != str(expected_count)
            or observed_run_digest != expected_shard_digest
        ):
            failed = True
            print(
                f"COMPOSITION_SHARD_FAIL shard={index}/{effective} "
                f"run_count={observed_run_count} run_ids_sha256={observed_run_digest} "
                f"expected_count={expected_count} "
                f"expected_ids_sha256={expected_shard_digest}",
                flush=True,
            )
        try:
            test_seconds = measured_shard_test_seconds(
                stdout,
                [test.id() for test in shards[index]],
                shard_count=effective,
                shard_index=index,
            )
        except PreflightFailure as exc:
            failed = True
            test_seconds = 0.0
            print(f"COMPOSITION_SHARD_FAIL {exc}", flush=True)
        shard_durations.append(duration)
        estimated_test_seconds.append(test_seconds)
        print(
            f"COMPOSITION_SHARD_RESULT shard={index}/{effective} "
            f"run_ids_sha256={observed_run_digest} wall_seconds={duration:.3f} "
            f"test_seconds={test_seconds:.3f} "
            f"exit_code={returncode}",
            flush=True,
        )
        if returncode != 0:
            failed = True
    if failed:
        raise PreflightFailure("one or more Composition core unittest shards failed")
    shard_wall = max(shard_durations, default=0.0)
    worker_seconds = sum(shard_durations)
    estimated_idle = max(0.0, effective * shard_wall - worker_seconds)
    timing_imbalance = max(estimated_test_seconds, default=0.0) - min(
        estimated_test_seconds, default=0.0
    )
    print(
        "COMPOSITION_WORKER_METRICS "
        f"requested={requested_jobs} effective={effective} peak_shard_workers={effective} "
        f"runner_wall_seconds={time.perf_counter() - started:.3f} "
        f"slowest_shard_seconds={shard_wall:.3f} "
        f"shard_worker_seconds={worker_seconds:.3f} "
        f"estimated_idle_worker_seconds={estimated_idle:.3f}",
        flush=True,
    )
    print(
        "COMPOSITION_SHARD_BALANCE "
        f"test_seconds_by_shard={','.join(f'{value:.3f}' for value in estimated_test_seconds)} "
        f"estimated_imbalance_seconds={timing_imbalance:.3f}",
        flush=True,
    )


def resolve_component_version_base(explicit: str | None) -> str:
    if explicit:
        return explicit
    configured = os.environ.get("COMPONENT_VERSION_BASE")
    if configured:
        return configured
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "origin/composition^{commit}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return "origin/composition"
    raise PreflightFailure(
        "component version base is required; pass --component-version-base or set "
        "COMPONENT_VERSION_BASE"
    )


def run_owned_validators(
    component_version_base: str,
    *,
    shard_count: int = DEFAULT_JOBS,
    include_integration_publication: bool = False,
    publication_already_validated: bool = False,
) -> None:
    checks: list[tuple[str, list[str]]] = []
    if not publication_already_validated:
        checks.append(
            (
                "playground-generated-state",
                command(
                    "scripts/generate_composition_playground_publication.py",
                    "--check-dir",
                    "generated",
                ),
            )
        )
        if include_integration_publication:
            checks.append(
                ("composition-publication", command("-I", "scripts/validate_publication.py"))
            )
    checks.extend(
        [
            ("translation-availability", command("-I", "scripts/validate_translations.py", "--allow-stale")),
            (
                "component-version-monotonicity",
                command("scripts/validate_component_versions.py", "--base", component_version_base),
            ),
            (
                "installer-release",
                command(
                    "-I",
                    "scripts/verify_composition_skill_installer_release.py",
                    "--git-ref",
                    "HEAD",
                ),
            ),
            (
                "core-test-partition",
                command(
                    "scripts/run_unittest_shard.py",
                    "--suite",
                    "core",
                    "--shard-count",
                    str(shard_count),
                    "--verify-only",
                ),
            ),
        ]
    )
    for name, argv in checks:
        run_check(name, argv)


def run_integration_publication_contract(protocol_root: Path) -> None:
    validator = protocol_root / "integration" / "publication_contract.py"
    if not validator.is_file():
        raise PreflightFailure(
            f"Integration publication protocol validator is missing: {validator}"
        )
    run_check(
        "publication-materialization",
        command("-I", "scripts/materialize_publication.py", "--source-root", "."),
    )
    run_check(
        "integration-publication-contract",
        command("-I", str(validator), "--source-root", "."),
    )


def run_consumer_spine() -> None:
    run_check("real-consumer-spine", command("-I", "scripts/run_composition_consumer_smoke.py"))


def run_focused_tests() -> None:
    run_consumer_spine()
    for path in FOCUSED_TESTS:
        if (ROOT / path).is_file():
            run_check(f"focused-{Path(path).stem}", command("-I", path))


def run_full_tests(requested_jobs: int = DEFAULT_JOBS) -> None:
    run_core_test_shards(requested_jobs)
    print(
        "COMPOSITION_WORKERS requested=1 effective=1 runner=composition-real-browser "
        "mode=serial-exclusive",
        flush=True,
    )
    run_real_browser_tests(resolve_chromedriver())
    for smoke in RUNTIME_SMOKES:
        run_check(Path(smoke).stem.replace("smoke_test_", ""), command("-I", smoke))


def require_clean_tree() -> None:
    status = git_output("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise PreflightFailure(
            "ready requires a clean index and working tree with no untracked files"
        )


def cleanup_ready_outputs() -> None:
    """Remove validation-only outputs produced by the local core suite."""

    if PUBLICATION_DESCRIPTOR.is_symlink() or PUBLICATION_DESCRIPTOR.is_file():
        PUBLICATION_DESCRIPTOR.unlink()
    elif PUBLICATION_DESCRIPTOR.exists():
        raise PreflightFailure(
            "ready produced a non-file publication descriptor that cannot be removed"
        )

    cache_directories: list[Path] = []
    bytecode_files: list[Path] = []
    for root in BYTECODE_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.name == "__pycache__":
                cache_directories.append(path)
            elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
                bytecode_files.append(path)
    for path in bytecode_files:
        path.unlink()
    for path in sorted(cache_directories, key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def run_core_ready(requested_jobs: int = DEFAULT_JOBS) -> None:
    shard_count = effective_core_jobs(requested_jobs)
    run_check(
        "core-discovery",
        command(
            "scripts/run_unittest_shard.py",
            "--suite",
            "core",
            "--shard-count",
            str(shard_count),
            "--verify-only",
        ),
    )
    run_core_test_shards(requested_jobs)


def run_playground_provenance(expected_head: str) -> None:
    with tempfile.TemporaryDirectory(prefix="composition-playground-ready-") as directory:
        output = Path(directory)
        base = output / "composition-playground-v1.json"
        intent = output / "composition-playground-intent-v1.json"
        run_check(
            "playground-base-projection",
            command("scripts/generate_composition_playground.py", "--output", str(base)),
        )
        run_check(
            "playground-intent-projection",
            command("scripts/generate_composition_playground_intent.py", "--output", str(intent)),
        )
        run_check(
            "playground-projection-provenance",
            command(
                "scripts/validate_playground_provenance.py",
                "--projection",
                str(base),
                "--projection",
                str(intent),
                "--expected-head",
                expected_head,
            ),
        )
    run_check(
        "playground-publication-provenance",
        command(
            "scripts/validate_playground_provenance.py",
            "--publication-dir",
            "generated",
        ),
    )


def run_dependency_boundary() -> None:
    run_check("dependency-boundary", command("scripts/check_python_dependencies.py"))


def run_ready(
    component_version_base: str,
    expected_head: str,
    jobs: int = DEFAULT_JOBS,
) -> None:
    """Run all cheap deterministic checks without Integration or browser inputs."""

    require_clean_tree()
    run_check("phase-zero-source", command("-I", "scripts/composition_phase_zero.py"))
    run_owned_validators(component_version_base, shard_count=effective_core_jobs(jobs))
    print(
        "COMPOSITION_PREFLIGHT_CHECK_DEFERRED name=composition-publication "
        "reason=reviewed Integration protocol checkout is an explicit cross-authority input",
        flush=True,
    )
    run_consumer_spine()
    run_core_ready(jobs)
    run_playground_provenance(expected_head)
    run_dependency_boundary()


def run_real_browser_tests(driver: str) -> None:
    browser_env = dict(os.environ)
    browser_env["CHROMEWEBDRIVER"] = driver
    run_check(
        "real-browser-tests",
        command(
            "scripts/run_unittest_shard.py",
            "--suite",
            "real-browser",
            "--shard-count",
            "1",
            "--shard-index",
            "0",
        ),
        env=browser_env,
    )


def resolve_chromedriver() -> str:
    configured_driver = os.environ.get("CHROMEWEBDRIVER") or shutil.which("chromedriver")
    if not configured_driver:
        raise PreflightFailure(
            "runner-provided ChromeDriver is required for the full Composition preflight"
        )
    driver_path = Path(configured_driver)
    if not driver_path.is_absolute() or not driver_path.is_file():
        raise PreflightFailure(
            "CHROMEWEBDRIVER or runner-provided chromedriver must name an existing "
            "absolute regular file"
        )
    return str(driver_path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("fast", "ready", "full"))
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        default=DEFAULT_JOBS,
        help=f"maximum local worker budget (default: {DEFAULT_JOBS}; core sharding caps at {MAX_CORE_SHARDS})",
    )
    parser.add_argument("--component-version-base")
    parser.add_argument("--expected-head")
    parser.add_argument("--integration-publication-protocol", type=Path)
    parser.add_argument(
        "--validators-only",
        action="store_true",
        help="run only the shared owned-validator stage used by sharded CI",
    )
    parser.add_argument(
        "--publication-already-validated",
        action="store_true",
        help=(
            "skip publication regeneration and publication semantics only when the "
            "same exact-head execution path already completed those checks"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        configure_validation_environment()
        head = git_output("rev-parse", "HEAD")
        requested_jobs = getattr(args, "jobs", DEFAULT_JOBS)
        effective = effective_core_jobs(requested_jobs)
        print(
            f"COMPOSITION_PREFLIGHT_START profile={args.profile} head={head} "
            f"requested_jobs={requested_jobs} effective_jobs={effective}",
            flush=True,
        )
        if args.expected_head and head != args.expected_head:
            raise PreflightFailure(
                f"exact-head mismatch: expected {args.expected_head}, found {head}"
            )
        if args.profile == "ready" and not args.expected_head:
            raise PreflightFailure("ready requires --expected-head")
        if args.publication_already_validated:
            if not args.validators_only:
                raise PreflightFailure(
                    "--publication-already-validated requires --validators-only"
                )
            if not PUBLICATION_DESCRIPTOR.is_file() or PUBLICATION_DESCRIPTOR.is_symlink():
                raise PreflightFailure(
                    "--publication-already-validated requires an existing non-symlink "
                    "generated/publication-descriptor.json from the same exact-head "
                    "execution path"
                )
        component_version_base = resolve_component_version_base(
            args.component_version_base
        )
        if args.integration_publication_protocol is not None:
            os.environ["INTEGRATION_PUBLICATION_PROTOCOL_ROOT"] = str(
                args.integration_publication_protocol.resolve()
            )
        if args.profile == "ready" and args.validators_only:
            raise PreflightFailure("ready does not support --validators-only")
        include_integration_publication = bool(
            args.integration_publication_protocol
            or os.environ.get("INTEGRATION_PUBLICATION_PROTOCOL_ROOT")
        )
        if args.profile == "ready":
            try:
                run_ready(component_version_base, head, requested_jobs)
            finally:
                cleanup_ready_outputs()
            print(f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} head={head}", flush=True)
            return 0
        if not args.validators_only:
            if args.profile == "full" and args.integration_publication_protocol is None:
                raise PreflightFailure("full preflight requires --integration-publication-protocol")
            # Reject source/environment failures before publication generation or core.
            run_check("phase-zero-source", command("-I", "scripts/composition_phase_zero.py"))
            if args.profile == "full":
                driver = resolve_chromedriver()
                run_check("phase-zero-browser", command("-I", "scripts/composition_phase_zero.py", "--driver", driver))
                os.environ["CHROMEWEBDRIVER"] = driver
        run_owned_validators(
            component_version_base,
            shard_count=effective,
            include_integration_publication=include_integration_publication,
            publication_already_validated=args.publication_already_validated,
        )
        if args.validators_only:
            print(
                f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} stage=validators head={head}",
                flush=True,
            )
            return 0
        if args.profile == "fast":
            print(
                f"COMPOSITION_WORKERS requested={requested_jobs} effective=1 "
                "runner=composition-fast mode=sequential-focused-checks",
                flush=True,
            )
            run_focused_tests()
        else:
            if args.integration_publication_protocol is None:
                raise PreflightFailure(
                    "full preflight requires --integration-publication-protocol pointing to "
                    "the pinned Integration publication protocol checkout"
                )
            # Full discovery contains the four focused modules.  Keep only the
            # distinct real-consumer spine before the broader core suite.
            run_consumer_spine()
            run_full_tests(requested_jobs)
            # Materialization intentionally runs after clean-source tests and
            # runtime smoke checks because it creates publication build products.
            run_integration_publication_contract(args.integration_publication_protocol.resolve())
        print(f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} head={head}", flush=True)
        return 0
    except (OSError, PreflightFailure) as exc:
        print(f"COMPOSITION_PREFLIGHT_FAIL: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
