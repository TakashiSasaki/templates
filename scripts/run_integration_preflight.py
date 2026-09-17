#!/usr/bin/env python3
"""Run canonical local Integration validation without provider network access."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


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


def validate_discovery() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test*.py", top_level_dir=str(ROOT))
    tests: list[object] = []

    def visit(value: object) -> None:
        if isinstance(value, unittest.TestSuite):
            for child in value:
                visit(child)
        else:
            tests.append(value)

    visit(suite)
    failed_imports = [test.id() for test in tests if test.id().startswith("unittest.loader._FailedTest")]
    if failed_imports:
        raise PreflightFailure("test discovery import failures: " + ", ".join(failed_imports))
    files = sorted((ROOT / "tests").glob("test_*.py"))
    imported_modules = {
        part
        for test in tests
        for part in test.id().split(".")
        if part.startswith("test_")
    }
    missing = [path.stem for path in files if path.stem not in imported_modules]
    if missing:
        raise PreflightFailure("test files not represented in discovery: " + ", ".join(missing))
    if not tests:
        raise PreflightFailure("Integration test discovery returned no tests")
    print(f"Integration test discovery: {len(tests)} cases across {len(files)} files", flush=True)
    return len(tests)


def run_fast(expected_head: str | None) -> None:
    require_exact_head(expected_head)
    run([str(PYTHON), "-m", "compileall", "-q", "integration", "publication_bundle", "ci_artifacts", "scripts", "tests"])
    run(command("scripts/check_python_dependencies.py"))
    validate_discovery()
    run([str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"])


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


def run_ready(expected_head: str) -> None:
    require_clean_tree()
    run_fast(expected_head)
    validate_publication_lock()
    validate_producer_identity(expected_head)
    fixture_round_trip()


def exact_revision(value: str, label: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise PreflightFailure(f"{label} must be a full lowercase commit SHA")
    return value


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
    run_fast(expected_head)
    validate_publication_lock()
    validate_producer_identity(expected_head)
    resolve_producer = importlib.import_module("scripts.resolve_producer_checkout")
    if resolve_producer.resolve_checkout(composition_root) != composition_revision:
        raise PreflightFailure("Composition checkout does not match its exact revision")
    if resolve_producer.resolve_checkout(policy_root) != policy_revision:
        raise PreflightFailure("Policy checkout does not match its exact revision")
    if modeling_root is not None and resolve_producer.resolve_checkout(modeling_root) != modeling_revision:
        raise PreflightFailure("Modeling checkout does not match its exact revision")
    materialization = [
        "scripts/materialize_publication_assets.py",
        "--publication", f"composition={composition_root}",
        "--publication", f"policy={policy_root}",
    ]
    if modeling_root is not None:
        materialization.extend(("--publication", f"modeling={modeling_root}"))
    run(command(*materialization))
    with tempfile.TemporaryDirectory(prefix="integration-preflight-providers-") as directory:
        output = Path(directory) / "publication-bundle"
        qualification = [
            "scripts/qualify_integration.py",
            "--integration-root", str(ROOT),
            "--producer-revision", expected_head,
            "--composition-root", str(composition_root),
            "--composition-revision", composition_revision,
            "--policy-root", str(policy_root),
            "--policy-revision", policy_revision,
        ]
        if modeling_root is not None:
            qualification.extend(("--modeling-root", str(modeling_root), "--modeling-revision", modeling_revision))
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
        if args.profile == "fast":
            run_fast(args.expected_head)
        else:
            if not args.expected_head:
                raise PreflightFailure(f"{args.profile} requires --expected-head")
            expected_head = exact_revision(args.expected_head, "expected head")
            if args.profile == "ready":
                run_ready(expected_head)
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
