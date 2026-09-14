#!/usr/bin/env python3
"""Run the canonical local and CI preflight for the Composition authority."""

from __future__ import annotations

import argparse
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
)
RUNTIME_SMOKES = (
    "scripts/smoke_test_runtime_distribution.py",
    "scripts/smoke_test_materialized_validation.py",
    "scripts/smoke_test_skill_runner.py",
    "scripts/smoke_test_remote_skill_installer.py",
)


class PreflightFailure(RuntimeError):
    """A named preflight check failed."""


def command(*args: str) -> list[str]:
    return [str(PYTHON), *args]


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


def run_owned_validators(component_version_base: str) -> None:
    checks = (
        (
            "playground-generated-state",
            command("scripts/generate_composition_playground_publication.py", "--check-dir", "generated"),
        ),
        ("composition-publication", command("-I", "scripts/validate_publication.py")),
        ("translation-freshness", command("-I", "scripts/validate_translations.py")),
        (
            "component-version-monotonicity",
            command("scripts/validate_component_versions.py", "--base", component_version_base),
        ),
        (
            "installer-release",
            command("-I", "scripts/verify_composition_skill_installer_release.py", "--git-ref", "HEAD"),
        ),
        (
            "core-test-partition",
            command("scripts/run_unittest_shard.py", "--suite", "core", "--shard-count", "2", "--verify-only"),
        ),
    )
    for name, argv in checks:
        run_check(name, argv)


def run_site_publication_contract(protocol_root: Path) -> None:
    validator = protocol_root / "scripts" / "publication_contract.py"
    if not validator.is_file():
        raise PreflightFailure(
            f"Site publication protocol validator is missing: {validator}"
        )
    run_check(
        "publication-materialization",
        command("-I", "scripts/materialize_publication.py", "--source-root", "."),
    )
    run_check(
        "site-publication-contract",
        command("-I", str(validator), "--source-root", "."),
    )


def run_focused_tests() -> None:
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
        run_real_browser_tests(str(driver_path.resolve()))
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
    parser.add_argument("profile", choices=("fast", "full"))
    parser.add_argument("--component-version-base")
    parser.add_argument("--expected-head")
    parser.add_argument("--site-publication-protocol", type=Path)
    parser.add_argument(
        "--validators-only",
        action="store_true",
        help="run only the shared owned-validator stage used by sharded CI",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        head = git_output("rev-parse", "HEAD")
        print(f"COMPOSITION_PREFLIGHT_START profile={args.profile} head={head}", flush=True)
        if args.expected_head and head != args.expected_head:
            raise PreflightFailure(
                f"exact-head mismatch: expected {args.expected_head}, found {head}"
            )
        component_version_base = resolve_component_version_base(
            args.component_version_base
        )
        if args.site_publication_protocol is not None:
            os.environ["SITE_PUBLICATION_PROTOCOL_ROOT"] = str(
                args.site_publication_protocol.resolve()
            )
        run_owned_validators(component_version_base)
        if args.validators_only:
            print(
                f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} stage=validators head={head}",
                flush=True,
            )
            return 0
        if args.profile == "fast":
            run_focused_tests()
        else:
            if args.site_publication_protocol is None:
                raise PreflightFailure(
                    "full preflight requires --site-publication-protocol pointing to "
                    "the pinned Site publication protocol checkout"
                )
            run_full_tests()
            # Materialization intentionally runs after clean-source tests and
            # runtime smoke checks because it creates publication build products.
            run_site_publication_contract(args.site_publication_protocol.resolve())
        print(f"COMPOSITION_PREFLIGHT_PASS profile={args.profile} head={head}", flush=True)
        return 0
    except (OSError, PreflightFailure) as exc:
        print(f"COMPOSITION_PREFLIGHT_FAIL: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
