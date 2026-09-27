#!/usr/bin/env python3
"""Run staged local Site validation.

Profiles:

* ``fast`` is a cheap development preflight and may inspect a dirty tree.
* ``source-ready`` is the clean, exact-commit gate for spending remote CI
  resources. It runs every repository-owned source check that needs no
  managed runtime, package installation, artifact, browser, or network.
* ``composition-validation`` runs the managed Composition consumer validator;
  Composition may provision its own validation runtime for this explicit
  boundary.
* ``artifact-local`` validates an already produced Bundle and rendered Site;
  both paths are required and no artifact is acquired or rendered.

Real browser/PWA acceptance, cross-authority acceptance, immutable artifact
qualification and GitHub/API aggregation remain remote acceptance checks.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.classify_site_ci import classify_paths
from scripts.site_check_registry import (
    ARTIFACT_LOCAL_CHECKS,
    CHECK_NAMES,
    MANAGED_VALIDATION_CHECKS,
    SOURCE_READY_CHECKS,
    playground_node_tests,
)


ROOT = Path(__file__).resolve().parents[1]
NODE_TESTS = playground_node_tests(ROOT)
CHECKS = CHECK_NAMES
PROFILES = {
    "fast": ("l0",),
    "source-ready": SOURCE_READY_CHECKS,
    "composition-validation": MANAGED_VALIDATION_CHECKS,
    "artifact-local": ARTIFACT_LOCAL_CHECKS,
}


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def _git_output(arguments: list[str]) -> tuple[str, ...]:
    output = subprocess.check_output(
        ["git", "-C", str(ROOT), *arguments],
        text=True,
    )
    return tuple(line for line in output.splitlines() if line)


def _changed_paths(base_ref: str, path_file: Path | None) -> tuple[str, ...]:
    candidates: list[str] = []
    if path_file is not None:
        candidates.extend(path_file.read_text(encoding="utf-8").splitlines())
    for arguments in (
        ["diff", "--name-only", "--no-renames", f"{base_ref}...HEAD"],
        ["diff", "--name-only", "--no-renames", "--cached"],
        ["diff", "--name-only", "--no-renames"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        candidates.extend(_git_output(arguments))
    return tuple(dict.fromkeys(path for path in candidates if path))


def _require_clean_source_ready_tree(expected_head: str | None, actual_head: str) -> None:
    if not expected_head:
        raise RuntimeError("source-ready requires --expected-head")
    if expected_head != actual_head:
        raise RuntimeError("exact Site head mismatch")
    status = _git_output(["status", "--porcelain=v1", "--untracked-files=all"])
    if status:
        raise RuntimeError(
            "source-ready requires a clean index and working tree with no untracked files"
        )


def run_l0(base_ref: str, path_file: Path | None) -> None:
    _run(["git", "diff", "--check", f"{base_ref}...HEAD"])
    _run(["git", "diff", "--cached", "--check"])
    _run(["git", "diff", "--check"])
    paths = _changed_paths(base_ref, path_file)
    if not paths:
        raise RuntimeError("L0 requires at least one changed path")
    classify_paths(paths)
    python_paths = [
        str(ROOT / path)
        for path in paths
        if path.endswith(".py") and (ROOT / path).is_file()
    ]
    if python_paths:
        _run([sys.executable, "-m", "py_compile", *python_paths])
    test_modules = [
        path[:-3].replace("/", ".")
        for path in paths
        if path.startswith("tests/test_") and path.endswith(".py")
    ]
    if test_modules:
        _run([sys.executable, "-m", "unittest", *test_modules])
    for path in paths:
        candidate = ROOT / path
        if candidate.is_file() and candidate.suffix == ".json":
            _run([sys.executable, "-m", "json.tool", str(candidate)])
        elif candidate.is_file() and candidate.suffix in {".yaml", ".yml"}:
            _validate_yaml(candidate)
        elif candidate.is_file() and candidate.suffix == ".toml":
            _validate_toml(candidate)


def _validate_yaml(path: Path) -> None:
    """Parse YAML without attempting to interpret GitHub expressions."""

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("YAML parser dependency PyYAML is unavailable") from exc
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RuntimeError(f"invalid YAML syntax in {path}: {exc}") from exc


def _validate_toml(path: Path) -> None:
    """Parse TOML, accounting for Site's generated navigation placeholder."""

    try:
        text = path.read_text(encoding="utf-8").replace("__GENERATED_NAV__", "[]")
        tomllib.loads(text)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"invalid TOML syntax in {path}: {exc}") from exc


def run_core() -> None:
    _run([sys.executable, "scripts/run_core_tests.py", "--suite", "core"])


def run_node(jobs: int = 1) -> None:
    if jobs < 1:
        raise ValueError("Site Node worker budget must be at least 1")
    if not NODE_TESTS:
        raise RuntimeError("no Composition Playground Node tests were found")
    effective_jobs = min(jobs, len(NODE_TESTS))
    environment = os.environ.copy()
    if environment.pop("NODE_OPTIONS", None) is not None:
        print("SITE_ENV_SANITIZED variable=NODE_OPTIONS runner=site-node reason=explicit-worker-budget", flush=True)
    print(
        f"SITE_WORKERS requested={jobs} effective={effective_jobs} "
        "runner=site-node mode=node-test",
        flush=True,
    )
    _run(
        ["node", "--test", f"--test-concurrency={effective_jobs}", *NODE_TESTS],
        env=environment,
    )


def run_site_contracts() -> None:
    _run([sys.executable, "scripts/validate_website_contracts.py", "."])
    _run([sys.executable, "scripts/validate_site_declarations.py", "."])


def run_dependency_boundary() -> None:
    _run([sys.executable, "scripts/check_python_dependencies.py"])


def run_composition_consumer() -> None:
    _run([sys.executable, ".template-composition/validate.py", "."])


def _require_artifact_inputs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.bundle is None or args.site_root is None:
        raise RuntimeError(
            "artifact-local validation requires both --bundle and --site-root"
        )
    return args.bundle, args.site_root


def run_exact_assembly(bundle: Path | None, site_root: Path | None) -> dict[str, str | int]:
    from scripts.check_site_artifact import check as check_site_artifact
    from site_renderer import acquire
    from site_renderer.bundle import load_lock
    from site_renderer.render import render

    lock = load_lock(ROOT / "integration-source.json")
    if (bundle is None) != (site_root is None):
        raise RuntimeError("--bundle and --site-root must be provided together")
    if bundle is not None and site_root is not None:
        return check_site_artifact(site_root, bundle, lock)

    with tempfile.TemporaryDirectory(prefix="site-ready-") as temporary:
        workspace = Path(temporary)
        receipt = acquire.locate(lock)
        if receipt is None:
            raise RuntimeError(
                "no exact qualified Integration Bundle artifact is available for "
                + lock["revision"]
            )
        accepted_bundle = workspace / "publication-bundle"
        acquire.consume(lock, receipt, accepted_bundle)
        output = workspace / "build"
        render(
            bundle=accepted_bundle,
            site_root=ROOT,
            output=output,
            expected_identity=lock["bundle_identity"],
        )
        return check_site_artifact(output / "site", accepted_bundle, lock)


def run_check(check: str, args: argparse.Namespace) -> None:
    if check == "l0":
        run_l0(args.base_ref, args.changed_paths)
    elif check == "core":
        run_core()
    elif check == "node":
        run_node(args.jobs)
    elif check == "site-contracts":
        run_site_contracts()
    elif check == "dependency-boundary":
        run_dependency_boundary()
    elif check == "composition-consumer":
        run_composition_consumer()
    elif check == "assembly":
        result = run_exact_assembly(args.bundle, args.site_root)
        print(json.dumps({"exact_site_assembly": result}, sort_keys=True))
    elif check == "bundle-reader":
        from scripts.check_bundle_reader import check as check_bundle_reader
        from site_renderer.bundle import load_lock

        bundle, site_root = _require_artifact_inputs(args)
        check_bundle_reader(site_root, bundle, load_lock(ROOT / "integration-source.json"))
    elif check == "site-artifact":
        from scripts.check_site_artifact import check as check_site_artifact
        from site_renderer.bundle import load_lock

        bundle, site_root = _require_artifact_inputs(args)
        result = check_site_artifact(
            site_root,
            bundle,
            load_lock(ROOT / "integration-source.json"),
        )
        print(json.dumps({"site_artifact": result}, sort_keys=True))
    else:  # pragma: no cover - argparse prevents this
        raise RuntimeError(f"unsupported local check: {check}")


def plan_source_ready_waves(
    jobs: int,
    *,
    core_workers: int = 1,
) -> list[list[tuple[str, int]]]:
    """Build a fixed, fail-closed worker allocation for independent source checks."""
    if jobs < 1:
        raise ValueError("Site worker budget must be at least 1")
    if core_workers < 1:
        raise ValueError("Site core allocation must be at least 1")

    node_capacity = len(NODE_TESTS)
    if node_capacity < 1:
        raise RuntimeError("no Composition Playground Node tests were found")

    core_allocation = min(core_workers, jobs)
    node_target = min(node_capacity, max(1, jobs // 2))
    waves: list[list[tuple[str, int]]] = []
    if core_allocation + node_target <= jobs:
        first_wave = [("core", core_allocation), ("node", node_target)]
        remaining = jobs - core_allocation - node_target
        for check in ("site-contracts", "dependency-boundary"):
            if remaining:
                first_wave.append((check, 1))
                remaining -= 1
        waves.append(first_wave)
    else:
        waves.append([("core", core_allocation)])
        waves.append([("node", min(node_capacity, jobs))])

    remaining_checks = ("site-contracts", "dependency-boundary")
    pending: list[tuple[str, int]] = []
    for check in remaining_checks:
        if any(check == name for wave in waves for name, _ in wave):
            continue
        pending.append((check, 1))
    for offset in range(0, len(pending), jobs):
        waves.append(pending[offset : offset + jobs])

    if any(not wave or sum(allocation for _, allocation in wave) > jobs for wave in waves):
        raise RuntimeError("Site source-ready allocation exceeds its worker budget")
    scheduled = [check for wave in waves for check, _ in wave]
    if scheduled != ["core", "node", *(check for check in remaining_checks if check in scheduled)]:
        raise RuntimeError("Site source-ready allocation changed deterministic check order")
    return waves


def _run_allocated_check(
    check: str,
    args: argparse.Namespace,
    allocation: int,
    wave_index: int,
) -> None:
    check_args = argparse.Namespace(**vars(args))
    check_args.jobs = allocation
    print(
        f"SITE_CHECK_START name={check} wave={wave_index} allocated_workers={allocation}",
        flush=True,
    )
    try:
        run_check(check, check_args)
    except Exception as exc:
        print(f"SITE_CHECK_FAIL name={check} error={exc}", file=sys.stderr, flush=True)
        raise
    print(f"SITE_CHECK_PASS name={check} wave={wave_index}", flush=True)


def _run_check_wave(
    wave: list[tuple[str, int]],
    args: argparse.Namespace,
    wave_index: int,
) -> None:
    allocations = sum(workers for _, workers in wave)
    print(
        f"SITE_WORKER_ALLOCATION requested={args.jobs} effective={allocations} "
        f"wave={wave_index} checks={','.join(f'{name}:{workers}' for name, workers in wave)}",
        flush=True,
    )
    if args.jobs == 1 or len(wave) == 1:
        for check, workers in wave:
            _run_allocated_check(check, args, workers, wave_index)
        return

    failures: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=len(wave), thread_name_prefix="site-check") as executor:
        futures = {
            executor.submit(_run_allocated_check, check, args, workers, wave_index): check
            for check, workers in wave
        }
        for future in as_completed(futures):
            check = futures[future]
            try:
                future.result()
            except Exception as exc:
                failures.append((check, exc))
    if failures:
        details = "; ".join(f"{check}: {failure}" for check, failure in failures)
        raise RuntimeError(f"Site source-ready wave {wave_index} failed: {details}")


def run_source_ready_dag(args: argparse.Namespace) -> None:
    """Run L0 first, then fixed-budget waves of checks that share only read-only source."""
    print("SITE_CHECK_START name=l0 wave=0 allocated_workers=1", flush=True)
    try:
        run_check("l0", argparse.Namespace(**{**vars(args), "jobs": 1}))
    except Exception as exc:
        print(f"SITE_CHECK_FAIL name=l0 error={exc}", file=sys.stderr, flush=True)
        raise
    print("SITE_CHECK_PASS name=l0 wave=0", flush=True)
    waves = plan_source_ready_waves(args.jobs)
    effective_jobs = max(sum(workers for _, workers in wave) for wave in waves)
    print(
        f"SITE_SOURCE_READY_BUDGET requested={args.jobs} effective={effective_jobs} "
        "python=unittest node=node-test",
        flush=True,
    )
    for index, wave in enumerate(waves, start=1):
        _run_check_wave(wave, args, index)


def positive_jobs(value: str) -> int:
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be an integer of at least 1")
    return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=PROFILES,
        help=(
            "fast=dirty-tree construction loop; source-ready=clean cheap source "
            "gate; composition-validation=managed Composition check; "
            "artifact-local=explicit Bundle/Site checks"
        ),
    )
    parser.add_argument("--check", action="append", choices=CHECKS)
    parser.add_argument("--expected-head")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--site-root", type=Path)
    parser.add_argument("--changed-paths", type=Path)
    parser.add_argument("--base-ref", default="HEAD^", help="base used for L0 changed-path checks")
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        default=2,
        metavar="N",
        help="maximum worker processes assigned to this Site runner (default: 2)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        head = "".join(_git_output(["rev-parse", "HEAD"]))
        if args.profile == "source-ready":
            _require_clean_source_ready_tree(args.expected_head, head)
        elif args.expected_head and args.expected_head != head:
            raise RuntimeError("exact Site head mismatch")
        if args.profile == "artifact-local":
            _require_artifact_inputs(args)
        checks = args.check or PROFILES[args.profile]
        if args.profile == "source-ready" and args.check is None:
            run_source_ready_dag(args)
        else:
            effective_jobs = min(args.jobs, len(NODE_TESTS)) if "node" in checks and NODE_TESTS else 1
            print(
                f"SITE_PREFLIGHT_WORKERS profile={args.profile} requested={args.jobs} "
                f"effective={effective_jobs} runner=site-preflight",
                flush=True,
            )
            for check in checks:
                run_check(check, args)
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
