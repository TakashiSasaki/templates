#!/usr/bin/env python3
"""Run staged local Site validation, including an exact Bundle-to-Site build.

Profiles:

* ``fast`` is a cheap development preflight and may inspect a dirty tree.
* ``full`` runs the local core, Node, exact assembly and artifact checks when
  explicit Bundle/Site inputs are supplied; it does not run browser acceptance.
* ``ready`` is the clean, exact-commit gate for spending remote CI resources.
  It requires ``--expected-head`` and runs core, applicable Node, exact Bundle
  assembly and generated-artifact checks. Browser/PWA acceptance remains a
  conditional/full CI responsibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.classify_site_ci import classify_paths


ROOT = Path(__file__).resolve().parents[1]
NODE_TESTS = tuple(
    str(path.relative_to(ROOT))
    for path in sorted((ROOT / "tests").glob("composition-playground*.test.mjs"))
)
CHECKS = ("l0", "core", "node", "node-explainability", "assembly", "bundle-reader", "site-artifact")
PROFILES = {
    "fast": ("l0",),
    "full": ("l0", "core", "node", "assembly"),
    "ready": ("l0", "core", "node", "assembly"),
}


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


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


def _require_clean_ready_tree(expected_head: str | None, actual_head: str) -> None:
    if not expected_head:
        raise RuntimeError("ready requires --expected-head")
    if expected_head != actual_head:
        raise RuntimeError("exact Site head mismatch")
    status = _git_output(["status", "--porcelain=v1", "--untracked-files=all"])
    if status:
        raise RuntimeError(
            "ready requires a clean index and working tree with no untracked files"
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


def run_core() -> None:
    _run([sys.executable, "scripts/run_core_tests.py", "--suite", "core"])


def run_node() -> None:
    if not NODE_TESTS:
        raise RuntimeError("no Composition Playground Node tests were found")
    _run(["node", "--test", *NODE_TESTS])


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
    elif check in {"node", "node-explainability"}:
        run_node()
    elif check == "assembly":
        result = run_exact_assembly(args.bundle, args.site_root)
        print(json.dumps({"exact_site_assembly": result}, sort_keys=True))
    elif check == "bundle-reader":
        from scripts.check_bundle_reader import check as check_bundle_reader
        from site_renderer.bundle import load_lock

        if args.bundle is None or args.site_root is None:
            raise RuntimeError("Bundle reader validation requires --bundle and --site-root")
        check_bundle_reader(args.site_root, args.bundle, load_lock(ROOT / "integration-source.json"))
    elif check == "site-artifact":
        from scripts.check_site_artifact import check as check_site_artifact
        from site_renderer.bundle import load_lock

        result = check_site_artifact(
            args.site_root,
            args.bundle,
            load_lock(ROOT / "integration-source.json") if args.bundle else None,
        )
        print(json.dumps({"site_artifact": result}, sort_keys=True))
    else:  # pragma: no cover - argparse prevents this
        raise RuntimeError(f"unsupported local check: {check}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=PROFILES,
        help="fast=dirty-tree L0; full=local assembly; ready=clean exact-head gate",
    )
    parser.add_argument("--check", action="append", choices=CHECKS)
    parser.add_argument("--expected-head")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--site-root", type=Path)
    parser.add_argument("--changed-paths", type=Path)
    parser.add_argument("--base-ref", default="HEAD^", help="base used for L0 changed-path checks")
    args = parser.parse_args(argv)
    try:
        head = "".join(_git_output(["rev-parse", "HEAD"]))
        if args.profile == "ready":
            _require_clean_ready_tree(args.expected_head, head)
        elif args.expected_head and args.expected_head != head:
            raise RuntimeError("exact Site head mismatch")
        checks = args.check or PROFILES[args.profile]
        for check in checks:
            run_check(check, args)
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
