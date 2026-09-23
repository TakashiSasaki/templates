#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

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

FOCUSED_TESTS = (
    "tests/test_config_driven_check.py",
    "tests/test_topology_contract_provenance.py",
    "tests/test_topology_change_orchestration.py",
    "tests/test_local_checkout_discovery.py",
    "tests/test_local_checkout_contract_provenance.py",
    "tests/test_observe_pr_state.py",
    "tests/test_pr_state_observation.py",
    "tests/test_pr_state_observation_replay.py",
    "tests/test_publish_review_artifacts.py",
    "tests/test_review_artifacts.py",
    "tests/test_review_scope_selection.py",
    "tests/test_maintainer_source_closure.py",
    "tests/test_live_review_adapter.py",
    "tests/test_maintainer_entrypoint_workflow.py",
    "tests/test_maintainer_efficiency_measurement.py",
    "tests/test_qualification_sequencing.py",
    "tests/test_preflight_orchestration.py",
    "tests/test_matched_policy_delivery.py",
    "tests/test_policy_delivery_evidence_spec.py",
    "tests/test_policy_delivery_evidence_consistency.py",
)


def sanitized_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIP_") and not key.startswith("PYTHON")
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


def check_focused_tests() -> None:
    missing = [path for path in FOCUSED_TESTS if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"focused Policy test suites are missing: {', '.join(missing)}")
    run(sys.executable, "-m", "pytest", *FOCUSED_TESTS)
    run(sys.executable, "scripts/check_policy_delivery_evidence.py")


def check_tests() -> None:
    run(sys.executable, "-m", "pytest")


def check_self() -> None:
    run(
        sys.executable,
        "-m",
        "agent_policy.cli",
        "--repository",
        str(ROOT),
        "check",
        "--config",
        ".agent-policy.yml",
    )


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
    protocol = Path(
        os.environ.get(
            "INTEGRATION_PUBLICATION_PROTOCOL",
            ".integration-publication-protocol/integration/publication_contract.py",
        )
    )
    if not protocol.is_absolute():
        protocol = ROOT / protocol
    if not protocol.is_file():
        raise RuntimeError(f"Integration publication protocol is unavailable: {protocol}")
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


def run_ready(base_ref: str, head: str) -> tuple[str, ...]:
    require_clean_tree()
    selected = list(PROFILES["full"])
    decision = classify_ready_applicability(base_ref, head)
    if decision.release_state_required:
        selected.append("release-state")
    if decision.trusted_review_required:
        selected.append("trusted-review")
    for name in selected:
        print(f"POLICY_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
        CHECKS[name]()
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


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run canonical Policy validation.")
    parser.add_argument("profile", nargs="?", choices=sorted(PROFILES), default="fast")
    parser.add_argument("--check", choices=sorted(CHECKS), action="append", dest="checks")
    parser.add_argument("--expected-head")
    parser.add_argument("--base-ref")
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
        if args.profile == "ready":
            if not args.expected_head:
                raise RuntimeError("ready requires --expected-head")
            if args.checks:
                raise RuntimeError(
                    "ready does not accept --check; use --base-ref for applicability"
                )
            if not args.base_ref:
                raise RuntimeError("ready requires --base-ref")
            selected = run_ready(args.base_ref, head)
        else:
            selected = tuple(args.checks or PROFILES[args.profile])
            for name in selected:
                print(f"POLICY_PREFLIGHT_CHECK_START name={name} head={head}", flush=True)
                CHECKS[name]()
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
