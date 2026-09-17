#!/usr/bin/env python3
"""Run the canonical local and CI preflight for the Composition authority."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
FOCUSED_TESTS = (
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


class PreflightFailure(RuntimeError):
    """A named preflight check failed."""


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
    publication_already_validated: bool = False,
) -> None:
    checks: list[tuple[str, list[str]]] = []
    if not publication_already_validated:
        checks.extend(
            [
                (
                    "playground-generated-state",
                    command(
                        "scripts/generate_composition_playground_publication.py",
                        "--check-dir",
                        "generated",
                    ),
                ),
                ("composition-publication", command("-I", "scripts/validate_publication.py")),
            ]
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
                    "2",
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


def run_full_tests() -> None:
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
    configured_driver = os.environ.get("CHROMEWEBDRIVER")
    if configured_driver:
        driver_path = Path(configured_driver)
        if not driver_path.is_absolute() or not driver_path.is_file():
            raise PreflightFailure(
                "CHROMEWEBDRIVER must name an existing absolute regular file"
            )
        run_real_browser_tests(str(driver_path))
    else:
        with tempfile.TemporaryDirectory(
            prefix="composition-preflight-chromedriver-"
        ) as directory:
            result = subprocess.run(
                command(
                    "-I", "scripts/prepare_chromedriver.py", "--output-dir", directory
                ),
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise PreflightFailure(f"browser-runtime-preparation failed: {detail}")
            driver = result.stdout.strip().splitlines()[-1]
            run_real_browser_tests(driver)
    for smoke in RUNTIME_SMOKES:
        run_check(Path(smoke).stem.replace("smoke_test_", ""), command("-I", smoke))


def require_clean_tree() -> None:
    status = git_output("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise PreflightFailure(
            "ready requires a clean index and working tree with no untracked files"
        )


def run_core_ready() -> None:
    run_check(
        "core-discovery",
        command(
            "scripts/run_unittest_shard.py",
            "--suite",
            "core",
            "--shard-count",
            "1",
            "--verify-only",
        ),
    )
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


def run_ready(component_version_base: str, expected_head: str) -> None:
    """Run all cheap deterministic checks without Integration or browser inputs."""

    require_clean_tree()
    run_check("phase-zero-source", command("-I", "scripts/composition_phase_zero.py"))
    run_owned_validators(component_version_base)
    run_consumer_spine()
    run_core_ready()
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("fast", "ready", "full"))
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
    resources = ExitStack()
    try:
        configure_validation_environment()
        head = git_output("rev-parse", "HEAD")
        print(f"COMPOSITION_PREFLIGHT_START profile={args.profile} head={head}", flush=True)
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
        if args.profile == "ready":
            run_ready(component_version_base, head)
            print(f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} head={head}", flush=True)
            return 0
        if not args.validators_only:
            if args.profile == "full" and args.integration_publication_protocol is None:
                raise PreflightFailure("full preflight requires --integration-publication-protocol")
            # Reject source/environment failures before publication generation or core.
            run_check("phase-zero-source", command("-I", "scripts/composition_phase_zero.py"))
            if args.profile == "full":
                driver = os.environ.get("CHROMEWEBDRIVER")
                if not driver:
                    directory = resources.enter_context(tempfile.TemporaryDirectory(prefix="composition-phase-zero-"))
                    result = subprocess.run(command("-I", "scripts/prepare_chromedriver.py", "--output-dir", directory),
                                            cwd=ROOT, text=True, capture_output=True, check=False)
                    if result.returncode:
                        raise PreflightFailure(f"browser-runtime-preparation failed: {result.stderr.strip()}")
                    driver = result.stdout.strip().splitlines()[-1]
                run_check("phase-zero-browser", command("-I", "scripts/composition_phase_zero.py", "--driver", driver))
                os.environ["CHROMEWEBDRIVER"] = driver
        run_owned_validators(
            component_version_base,
            publication_already_validated=args.publication_already_validated,
        )
        if args.validators_only:
            print(
                f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} stage=validators head={head}",
                flush=True,
            )
            return 0
        if args.profile == "fast":
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
            run_full_tests()
            # Materialization intentionally runs after clean-source tests and
            # runtime smoke checks because it creates publication build products.
            run_integration_publication_contract(args.integration_publication_protocol.resolve())
        print(f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} head={head}", flush=True)
        return 0
    except (OSError, PreflightFailure) as exc:
        print(f"COMPOSITION_PREFLIGHT_FAIL: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        resources.close()


if __name__ == "__main__":
    raise SystemExit(main())
