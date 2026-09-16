#!/usr/bin/env python3
"""Run the canonical local and CI preflight for the Site authority."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
import json
import shutil
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.resolve_publication_sources import resolve_sources
from scripts.classify_site_ci import classify_paths, ClassificationError


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
    capsule = getattr(args, "capsule", None) if args is not None else None
    descriptor = capsule.inherited_fd if capsule is not None else None
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment(args),
        check=False,
        pass_fds=() if descriptor is None else (descriptor,),
    )
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


@contextmanager
def capsule_source_snapshot(args: argparse.Namespace, stage: str):
    """Run one cacheable stage from source bytes frozen at its input identity.

    A capsule lock protects its entry, not the working trees.  Cloning each
    repository at its recorded revision and then overlaying the working tree
    gives the stage an immutable copy of tracked, dirty, untracked, generated,
    and catalog-declared inputs.  Re-identifying the copy rejects a source
    change observed while the snapshot was made; a transient change that is
    restored later cannot affect the stage unless it was captured, in which
    case its identity differs and fails closed.
    """
    if not getattr(args, "capsule", None):
        yield
        return
    from scripts.local_qualification_capsule import input_identity, source_paths

    original_root = ROOT
    original_composition = args.composition_root
    original_policy = args.policy_root
    # Keep source snapshots in a mode-0700 temporary directory rather than
    # below the descriptor-addressed cache entry: subprocesses which inspect a
    # snapshot with Git do not inherit that descriptor unless they are an
    # explicit capsule consumer.
    snapshot_root = Path(tempfile.mkdtemp(prefix=f"site-capsule-{stage}-"))
    snapshots: dict[str, Path] = {}
    descriptor = args.capsule.inherited_fd
    try:
        for name, source in args.capsule_roots.items():
            destination = snapshot_root / name
            revision = args.capsule.inputs["sources"][name]["revision"]
            subprocess.run(
                ["git", "clone", "--shared", "--no-checkout", str(source), str(destination)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                pass_fds=() if descriptor is None else (descriptor,),
            )
            subprocess.run(
                ["git", "-C", str(destination), "checkout", "--detach", "--force", revision],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                pass_fds=() if descriptor is None else (descriptor,),
            )
            for child in destination.iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            # Do not copy an ignored file merely because it exists in the
            # checkout.  A cached stage may read every test or build input it
            # can see; the snapshot therefore exposes exactly the files that
            # participate in ``source_identity`` and no unbound extras.
            for raw_relative in source_paths(source):
                relative = Path(os.fsdecode(raw_relative))
                original = source / relative
                if not original.exists() and not original.is_symlink():
                    continue
                copied = destination / relative
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, copied, follow_symlinks=False)
            snapshots[name] = destination
        if input_identity(snapshots) != args.capsule.inputs:
            raise PreflightFailure("capsule inputs changed while snapshotting")
        globals()["ROOT"] = snapshots["site"]
        args.composition_root = snapshots["composition"]
        args.policy_root = snapshots["policy"]
        yield
    finally:
        globals()["ROOT"] = original_root
        args.composition_root = original_composition
        args.policy_root = original_policy
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root)


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


def focused_tests(paths: Sequence[str]) -> tuple[str, ...]:
    """Local diagnostics only; never emits remote skip authority."""
    try:
        decision = classify_paths(paths)
    except ClassificationError:
        return ()  # empty selection means the complete core suite
    if decision.full_required:
        return ()
    selected = set(FOCUSED_TESTS)
    if decision.browser_required or decision.publication_required:
        selected.update(("tests.test_audience_artifact_integration",
                         "tests.test_audience_manifest", "tests.test_audience_context",
                         "tests.test_check_audience_runtime"))
    if decision.reference_consumer_required:
        selected.update(("tests.test_reference_consumer", "tests.test_reference_browser_contracts"))
    if decision.publication_required or decision.cross_authority_required:
        selected.update(("tests.test_site_assembly", "tests.test_optional_document_source_type"))
    return tuple(sorted(selected))


def changed_paths(base: str | None) -> list[str]:
    if not base:
        return []
    result = subprocess.run(["git", "diff", "--name-only", "-z", base],
                            cwd=ROOT, capture_output=True, check=True)
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                               cwd=ROOT, capture_output=True, check=True)
    return [p.decode("utf-8") for p in (result.stdout + untracked.stdout).split(b"\0") if p]


def check_focused_tests(args: argparse.Namespace) -> None:
    selected = focused_tests(changed_paths(getattr(args, "base", None)))
    if selected:
        run(PYTHON, "-m", "unittest", *selected, "--verbose", args=args)
    else:
        run(PYTHON, "scripts/run_core_tests.py", "--suite", "core", args=args)


def check_audience_static(args: argparse.Namespace) -> None:
    composition, policy = require_provider_roots(args)
    if getattr(args, "capsule", None):
        args.capsule.verify_artifact()
        args.site_root = args.capsule.artifact
    if args.site_root is None:
        raise PreflightFailure("audience-static requires --site-root with an assembled artifact")
    run(PYTHON, "scripts/check_audience_artifact.py", "--site-root", args.site_root,
        "--composition-root", composition, "--policy-root", policy, args=args)


def check_audience_browser(args: argparse.Namespace) -> None:
    composition, policy = require_provider_roots(args)
    if args.capsule:
        args.capsule.verify_artifact()
        artifact = args.capsule.artifact
        output = args.capsule.workspace / "audience-browser.json"
    elif args.site_root:
        artifact = args.site_root
        output = artifact.parent / "audience-browser.json"
    else:
        raise PreflightFailure("audience-browser requires a capsule or --site-root")
    run(PYTHON, "scripts/check_audience_runtime.py", "--site-root", artifact,
        "--composition-root", composition, "--policy-root", policy,
        "--output", output, "--channel", args.channel, args=args)


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


def check_integration_tests(args: argparse.Namespace) -> None:
    require_provider_roots(args)
    run(PYTHON, "scripts/run_core_tests.py", "--suite", "integration", "--verbose", args=args)


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
    for provider_root in (composition, policy):
        catalog = provider_root / "docs" / "publication-catalog.json"
        try:
            schema_version = json.loads(catalog.read_text(encoding="utf-8")).get("schema_version")
        except (OSError, json.JSONDecodeError) as exc:
            raise PreflightFailure(f"unable to read publication catalog {catalog}: {exc}") from exc
        if schema_version == 3:
            run(PYTHON, "scripts/publication_contract.py", "--source-root", provider_root)
        elif schema_version == 4:
            # Ready preflight runs before materialization, so generated v4 assets
            # may legitimately be absent while every tracked source is validated.
            run(
                PYTHON,
                "scripts/publication_contract_v4.py",
                "--source-root",
                provider_root,
                "--phase",
                "source",
            )
        else:
            raise PreflightFailure(
                f"publication catalog schema must be 3 or 4: {catalog}"
            )
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
    retained = getattr(args, "capsule", None)
    context = nullcontext(str(retained.workspace)) if retained else tempfile.TemporaryDirectory(prefix="site-preflight-")
    with context as directory:
        temporary = Path(directory)
        site_publication = temporary / "site-publication"
        build = temporary / "build"
        if retained:
            for path in (site_publication, build):
                if path.exists():
                    shutil.rmtree(path)
        run(
            PYTHON,
            "scripts/prepare_repository_tree_publication.py",
            "--site-root",
            ROOT,
            "--output-root",
            site_publication,
            args=args,
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
            "--site-source-root",
            ROOT,
            "--output-root",
            build,
            args=args,
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
            args=args,
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
            args=args,
        )
        run(
            ZENSICAL,
            "build",
            "--config-file",
            build / "zensical.toml",
            "--clean",
            "--strict",
            args=args,
        )
        run(PYTHON, "scripts/finalize_site_metadata.py", "--site-root", build / "site",
            "--canonical-url", "https://templates.moukaeritai.work/", args=args)
        run(PYTHON, "scripts/render_website_metadata.py", "--repository", ROOT, "--site-root", build / "site", args=args)
        run(PYTHON, "scripts/finalize_translation_reader.py", "--site-root", build / "site",
            "--translation-map", build / "translation-publication.json",
            "--canonical-url", "https://templates.moukaeritai.work/", args=args)
        run(PYTHON, "scripts/write_publication_provenance.py", "--output", build / "site/build-provenance.json",
            "--repository", "TakashiSasaki/templates", "--site-commit", git_head(ROOT),
            "--publication-commit", f"composition={git_head(composition)}",
            "--publication-commit", f"policy={git_head(policy)}", args=args)
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
    "audience-static": check_audience_static,
    "audience-browser": check_audience_browser,
    "reference-projections": check_reference_projections,
    "website-contract": check_website_contract,
    "focused-tests": check_focused_tests,
    "unit-tests": check_unit_tests,
    "integration-tests": check_integration_tests,
    "node-explainability": check_node_explainability,
    "materialization-tests": check_materialization_tests,
    "publication-contract-tests": check_publication_contract_tests,
    "cross-binding": check_cross_binding,
    "provider-tests": check_provider_tests,
    "candidate-projection": check_candidate_projection,
    "cross-assembly": check_cross_assembly,
}

PROFILES = {
    "ready": ("focused-tests", "cross-binding", "cross-assembly", "audience-static"),
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
    parser.add_argument("--base", help="Exact comparison revision for local capability selection")
    parser.add_argument("--site-root", type=Path)
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--capsule-root", type=Path, help="Disposable local cache outside every source checkout")
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
    if args.profile == "ready" and args.site_root and not args.checks:
        selected = ("focused-tests", "audience-static")
    args.capsule = None
    try:
        if args.capsule_root:
            from scripts.local_qualification_capsule import Capsule, input_identity
            composition, policy = require_provider_roots(args)
            roots = {"site": ROOT, "composition": composition, "policy": policy}
            target = args.capsule_root.resolve()
            if any(target == root.resolve() or root.resolve() in target.parents for root in roots.values()):
                raise PreflightFailure("capsule must be outside all source checkouts")
            args.capsule_roots = roots
            args.capsule = Capsule(target, input_identity(roots))
        with args.capsule.locked() if args.capsule else nullcontext():
            if args.capsule:
                from scripts.local_qualification_capsule import input_identity
                if input_identity(args.capsule_roots) != args.capsule.inputs:
                    raise PreflightFailure("capsule inputs changed before validation")
            return execute_checks(args, selected, head)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SITE_PREFLIGHT_FAIL error={exc}", file=sys.stderr)
        return 1


def execute_checks(args, selected, head):
    try:
        for name in selected:
            print(f"SITE_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
            if args.capsule and name in {"cross-assembly", "focused-tests", "audience-static", "audience-browser", "unit-tests"}:
                from scripts.local_qualification_capsule import input_identity
                if input_identity(args.capsule_roots) != args.capsule.inputs:
                    raise PreflightFailure("capsule inputs changed before stage reuse")
                stage = "build" if name == "cross-assembly" else name
                from scripts.local_qualification_capsule import input_identity
                def validate_capsule_inputs():
                    if input_identity(args.capsule_roots) != args.capsule.inputs:
                        raise PreflightFailure("capsule inputs changed during validation")
                validate_capsule_inputs()
                def operation():
                    with capsule_source_snapshot(args, stage):
                        CHECKS[name](args)
                    validate_capsule_inputs()
                args.capsule.stage(stage, operation, artifact=name in {"audience-static", "audience-browser"},
                                   reuse=name not in {"focused-tests", "audience-browser"},
                                   validate_reuse=validate_capsule_inputs)
            else:
                CHECKS[name](args)
            print(f"SITE_PREFLIGHT_CHECK_PASS name={name} head={head}", flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
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
