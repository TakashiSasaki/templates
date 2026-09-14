#!/usr/bin/env python3
"""Run the canonical local and CI preflight for the Site authority."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.resolve_publication_sources import resolve_sources


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
ZENSICAL = PYTHON.with_name("zensical")
FOCUSED_TESTS = (
    "tests.test_topology_publication_routing",
    "tests.test_ledger_overview",
    "tests.test_site_owned_translations",
    "tests.test_reference_consumer",
    "tests.test_reference_browser_contracts",
    "tests.test_publication_freshness_workflow",
    "tests.test_composition_playground_cross_authority_workflow",
)
NODE_EXPLAINABILITY_TESTS = (
    "tests/composition-playground.test.mjs",
    "tests/composition-playground-final-remediation.test.mjs",
    "tests/composition-playground-hash-copy-review.test.mjs",
    "tests/composition-playground-final-three-review.test.mjs",
    "tests/composition-playground-latest-review.test.mjs",
    "tests/composition-playground-root-reachability.test.mjs",
    "tests/composition-playground-latest-five-review.test.mjs",
    "tests/composition-playground-explain.test.mjs",
    "tests/composition-playground-topology.test.mjs",
)


class PreflightFailure(RuntimeError):
    """A named Site preflight check failed."""


def environment(args: argparse.Namespace | None = None) -> dict[str, str]:
    result = dict(os.environ)
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTHONPATH"] = str(ROOT)
    if args is not None and args.composition_root is not None:
        result["SITE_COMPOSITION_ROOT"] = str(args.composition_root.resolve())
    if args is not None and args.policy_root is not None:
        result["SITE_POLICY_ROOT"] = str(args.policy_root.resolve())
    return result


def run(*arguments: str, args: argparse.Namespace | None = None) -> None:
    command = [str(argument) for argument in arguments]
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=environment(args), check=False)
    if completed.returncode != 0:
        raise PreflightFailure(
            f"{' '.join(command)} failed with exit code {completed.returncode}"
        )


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PreflightFailure(
            f"unable to resolve Git HEAD for {root}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def require_provider_roots(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.composition_root is None or args.policy_root is None:
        raise PreflightFailure(
            "this check requires --composition-root and --policy-root at the locked revisions"
        )
    return args.composition_root.resolve(strict=True), args.policy_root.resolve(strict=True)


def require_composition_root(args: argparse.Namespace) -> Path:
    if args.composition_root is None:
        raise PreflightFailure("this check requires --composition-root at the locked revision")
    return args.composition_root.resolve(strict=True)


def check_reference_projections(args: argparse.Namespace) -> None:
    run(PYTHON, "scripts/render_reference_consumer.py")
    run(PYTHON, "scripts/site_website_contract.py")
    if args.composition_root is not None or args.policy_root is not None:
        composition, policy = require_provider_roots(args)
        run(
            PYTHON,
            "scripts/generate_agent_bootstrap.py",
            "--site-root",
            ROOT,
            "--composition-root",
            composition,
            "--policy-root",
            policy,
        )


def check_website_contract(args: argparse.Namespace) -> None:
    del args
    run(PYTHON, "scripts/validate_website_contracts.py", ROOT)
    run(PYTHON, "scripts/validate_website_evidence.py", ROOT)
    run(PYTHON, ".template-composition/validate.py", ROOT)


def check_focused_tests(args: argparse.Namespace) -> None:
    del args
    run(PYTHON, "-m", "unittest", *FOCUSED_TESTS, "--verbose")


def check_unit_tests(args: argparse.Namespace) -> None:
    run(
        PYTHON,
        "-m",
        "unittest",
        "discover",
        "--start-directory",
        "tests",
        "--verbose",
        args=args,
    )


def check_node_explainability(args: argparse.Namespace) -> None:
    del args
    for test in NODE_EXPLAINABILITY_TESTS:
        run("node", "--test", test)


def check_materialization_tests(args: argparse.Namespace) -> None:
    del args
    run(
        PYTHON,
        "-m",
        "unittest",
        "tests.test_materialize_publication_assets",
        "tests.test_materialize_publication_assets_review_followup",
        "tests.test_assembly_materialization_boundary",
        "--verbose",
    )


def check_publication_contract_tests(args: argparse.Namespace) -> None:
    del args
    run(
        PYTHON,
        "-m",
        "unittest",
        "tests.test_publication_contract",
        "tests.test_publication_contract_v4",
        "tests.test_audience_inventory",
        "--verbose",
    )
    run(PYTHON, "scripts/validate_audience_inventory.py", "--fetch-audit")


def check_cross_binding(args: argparse.Namespace) -> None:
    composition, policy = require_provider_roots(args)
    revisions = resolve_sources(ROOT / "publication-sources.json", {})
    actual = {
        "composition": git_head(composition),
        "policy": git_head(policy),
    }
    for provider, expected in revisions.items():
        if actual[provider] != expected:
            raise PreflightFailure(
                f"{provider} checkout mismatch: expected {expected}, found {actual[provider]}"
            )
    run(
        PYTHON,
        "scripts/generate_agent_bootstrap.py",
        "--site-root",
        ROOT,
        "--composition-root",
        composition,
        "--policy-root",
        policy,
    )
    run(PYTHON, "scripts/publication_contract.py", "--source-root", composition)
    run(PYTHON, "scripts/publication_contract.py", "--source-root", policy)
    print(
        "SITE_CROSS_AUTHORITY_BINDING "
        f"composition={actual['composition']} policy={actual['policy']}",
        flush=True,
    )


def check_provider_tests(args: argparse.Namespace) -> None:
    composition, policy = require_provider_roots(args)
    run(
        PYTHON,
        "scripts/materialize_publication_assets.py",
        "--publication",
        f"composition={composition}",
        "--publication",
        f"policy={policy}",
    )
    run(
        PYTHON,
        "scripts/run_core_tests.py",
        "--suite",
        "provider",
        "--verbose",
        args=args,
    )


def check_candidate_projection(args: argparse.Namespace) -> None:
    composition = require_composition_root(args)
    expected = resolve_sources(ROOT / "publication-sources.json", {})["composition"]
    actual = git_head(composition)
    if actual != expected:
        raise PreflightFailure(
            f"composition checkout mismatch: expected {expected}, found {actual}"
        )
    run(
        "node",
        "scripts/check_composition_playground_candidate_projection.mjs",
        composition,
    )


def check_cross_assembly(args: argparse.Namespace) -> None:
    composition, policy = require_provider_roots(args)
    with tempfile.TemporaryDirectory(prefix="site-preflight-") as directory:
        temporary = Path(directory)
        site_publication = temporary / "site-publication"
        build = temporary / "build"
        run(
            PYTHON,
            "scripts/prepare_repository_tree_publication.py",
            "--site-root",
            ROOT,
            "--output-root",
            site_publication,
        )
        run(
            PYTHON,
            "scripts/assemble_publications_v3.py",
            "--publication",
            f"site={site_publication}",
            "--publication",
            f"composition={composition}",
            "--publication",
            f"policy={policy}",
            "--site-root",
            site_publication,
            "--output-root",
            build,
        )
        run(
            PYTHON,
            "scripts/publish_provider_translations.py",
            "--reader-navigation-locales",
            ROOT / "reader-navigation-locales.json",
            "--publication",
            f"site={site_publication}",
            "--publication",
            f"composition={composition}",
            "--publication",
            f"policy={policy}",
            "--site-root",
            site_publication,
            "--output-root",
            build,
        )
        run(
            PYTHON,
            "scripts/prepare_site_metadata.py",
            "--config-file",
            build / "zensical.toml",
            "--deployment-timestamp",
            "",
            "--canonical-url",
            "https://templates.moukaeritai.work/",
        )
        run(
            ZENSICAL,
            "build",
            "--config-file",
            build / "zensical.toml",
            "--clean",
            "--strict",
        )
        for relative in (
            "site/index.html",
            "site/workspace/index.html",
            "site/workspace/bare-worktree/index.html",
            "site/workspace/architecture/index.html",
        ):
            target = build / relative
            if not target.is_file():
                raise PreflightFailure(f"static documentation build omitted {relative}")


CHECKS: dict[str, Callable[[argparse.Namespace], None]] = {
    "reference-projections": check_reference_projections,
    "website-contract": check_website_contract,
    "focused-tests": check_focused_tests,
    "unit-tests": check_unit_tests,
    "node-explainability": check_node_explainability,
    "materialization-tests": check_materialization_tests,
    "publication-contract-tests": check_publication_contract_tests,
    "cross-binding": check_cross_binding,
    "provider-tests": check_provider_tests,
    "candidate-projection": check_candidate_projection,
    "cross-assembly": check_cross_assembly,
}

PROFILES = {
    "fast": ("reference-projections", "website-contract", "focused-tests"),
    "full": (
        "reference-projections",
        "website-contract",
        "unit-tests",
        "node-explainability",
        "cross-binding",
        "candidate-projection",
        "cross-assembly",
    ),
    "cross": (
        "cross-binding",
        "candidate-projection",
        "provider-tests",
        "cross-assembly",
    ),
}


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="?", choices=sorted(PROFILES), default="fast")
    parser.add_argument("--check", choices=sorted(CHECKS), action="append", dest="checks")
    parser.add_argument("--expected-head")
    parser.add_argument("--composition-root", type=Path)
    parser.add_argument("--policy-root", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    head = git_head(ROOT)
    if args.expected_head and head != args.expected_head:
        print(
            f"SITE_PREFLIGHT_FAIL head={head} expected={args.expected_head} reason=head-mismatch",
            file=sys.stderr,
        )
        return 1
    selected = tuple(args.checks or PROFILES[args.profile])
    try:
        for name in selected:
            print(f"SITE_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
            CHECKS[name](args)
            print(f"SITE_PREFLIGHT_CHECK_PASS name={name} head={head}", flush=True)
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            f"SITE_PREFLIGHT_FAIL profile={args.profile} head={head} error={exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"SITE_PREFLIGHT_PASS profile={args.profile} head={head} "
        f"checks={','.join(selected)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
