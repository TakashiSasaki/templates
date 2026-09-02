#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import venv
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_REQUIREMENTS = ROOT / "release/verifier-requirements.lock"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*$"
)
RISK_DOMAIN_REFERENCE_PATHS = (
    "skills/pr-review/references/risk-domains/index.md",
    "skills/pr-review/references/risk-domains/identity-and-authority.md",
    "skills/pr-review/references/risk-domains/namespace-and-indirection.md",
    "skills/pr-review/references/risk-domains/state-mutation-and-recovery.md",
    "skills/pr-review/references/risk-domains/concurrency-and-temporal-consistency.md",
    "skills/pr-review/references/risk-domains/privileged-execution.md",
    "skills/pr-review/references/risk-domains/persistence-and-integrity.md",
    "skills/pr-review/references/risk-domains/external-interaction.md",
    "skills/pr-review/references/risk-domains/resource-behavior.md",
    "skills/pr-review/references/risk-domains/build-provenance-and-ci.md",
    "skills/pr-review/references/risk-domains/consumer-and-execution-paths.md",
)
RISK_DOMAIN_BUNDLE_PATHS = tuple(
    "procedure/" + path.removeprefix("skills/pr-review/")
    for path in RISK_DOMAIN_REFERENCE_PATHS
)
TRUSTED_REVIEW_REQUIRED_PATHS = (
    "skills/agent-policy/SKILL.md",
    "skills/agent-policy/scripts/review_base.py",
    "skills/agent-policy/scripts/run.py",
    "skills/agent-policy/scripts/runtime_image.py",
    "skills/pr-review/SKILL.md",
    "skills/pr-review/references/github-pull-request-review-api.md",
    *RISK_DOMAIN_REFERENCE_PATHS,
    "src/agent_policy/commands/review_bundle.py",
    "templates/policy-context.md.j2",
)

TRUSTED_REVIEW_PROBE = r'''
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from agent_policy.commands import check, render, review_bundle, validate

revision = os.environ["TRUSTED_REVIEW_CANDIDATE_REVISION"]
semantic_output = ".review-authority/review-policy.md"
policy = """---
id: project.candidate-review
severity: mandatory
overridable: true
order: 1000
---
# Candidate review rule

Exercise the exact promotion candidate review context.
"""

with tempfile.TemporaryDirectory(prefix="agent-policy-trusted-review-candidate-") as temporary:
    workspace = Path(temporary)
    trusted_base = workspace / "trusted-base"
    trusted_base.mkdir()
    (trusted_base / "policy").mkdir()
    (trusted_base / "policy/review.md").write_text(policy, encoding="utf-8")
    (trusted_base / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {revision}
contexts:
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - policy/review.md
outputs:
  review-authority:
    enabled: true
    path: {semantic_output}
    context: review
    renderer: policy-context-md
skills:
  enabled:
    - pr-review
""",
        encoding="utf-8",
    )

    validate_codes = [
        item.code for item in validate.run(trusted_base, ".agent-policy.yml")
    ]
    render_codes = [
        item.code for item in render.run(trusted_base, ".agent-policy.yml")
    ]
    check_codes = [
        item.code for item in check.run(trusted_base, ".agent-policy.yml")
    ]

    bundle = workspace / "review-authority-bundle"
    materialize_codes = [
        item.code
        for item in review_bundle.materialize(
            trusted_base,
            ".agent-policy.yml",
            bundle,
            semantic_output,
        )
    ]
    verify_codes = [
        item.code
        for item in review_bundle.verify(
            trusted_base,
            ".agent-policy.yml",
            bundle,
            semantic_output,
        )
    ]

    files = sorted(
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    )
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    procedure = (bundle / "procedure/SKILL.md").read_text(encoding="utf-8")
    semantic = (bundle / "semantic/review-policy.md").read_text(encoding="utf-8")
    forbidden_result_fields = {
        "schema_version",
        "analysis_status",
        "comments",
        "unanchored_findings",
    }

    print(
        json.dumps(
            {
                "validate": validate_codes,
                "render": render_codes,
                "check": check_codes,
                "materialize": materialize_codes,
                "verify": verify_codes,
                "files": files,
                "manifest_bundle_format": manifest.get("bundle_format"),
                "manifest_has_adapter": "adapter" in manifest,
                "manifest_has_result_fields": bool(
                    forbidden_result_fields.intersection(manifest)
                ),
                "semantic_has_local_rule": "project.candidate-review" in semantic,
                "semantic_has_shared_review": "review.require-change-causality" in semantic,
                "procedure_has_identity_refresh": (
                    "Refresh all live identities immediately before completion" in procedure
                ),
                "procedure_stops_before_merge": "Stop before merge authorization" in procedure,
            },
            sort_keys=True,
        )
    )
'''


def git_text(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def locked_requirements(path: Path) -> tuple[str, ...]:
    requirements = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not requirements:
        raise ValueError("Trusted review candidate verifier requirements must not be empty")
    names: set[str] = set()
    for requirement in requirements:
        if EXACT_REQUIREMENT.fullmatch(requirement) is None:
            raise ValueError(
                "Trusted review candidate verifier requirements must use exact "
                f"name==version pins: {requirement}"
            )
        name = requirement.split("==", 1)[0].lower().replace("_", "-")
        if name in names:
            raise ValueError(
                f"Trusted review candidate verifier requirement is duplicated: {requirement}"
            )
        names.add(name)
    return requirements


def resolve_candidate_revision(git_ref: str) -> str:
    revision = git_text("rev-parse", f"{git_ref}^{{commit}}")
    if FULL_SHA.fullmatch(revision) is None:
        raise ValueError("Trusted review candidate must resolve to one full lowercase commit SHA")
    return revision


@contextmanager
def extracted_revision(revision: str) -> Iterator[Path]:
    if FULL_SHA.fullmatch(revision) is None:
        raise ValueError("Trusted review candidate revision must be a full lowercase commit SHA")
    with tempfile.TemporaryDirectory(prefix="agent-policy-review-candidate-tree-") as temporary:
        root = Path(temporary)
        archive_path = root / "candidate.tar"
        tree = root / "tree"
        tree.mkdir()
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar",
                f"--output={archive_path}",
                revision,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        with tarfile.open(archive_path, "r") as archive:
            archive.extractall(tree, filter="data")
        yield tree


def probe_python_path(environment_root: Path) -> Path:
    if os.name == "nt":
        return environment_root / "Scripts/python.exe"
    return environment_root / "bin/python"


@contextmanager
def isolated_probe_environment() -> Iterator[Path]:
    locked_requirements(VERIFIER_REQUIREMENTS)
    with tempfile.TemporaryDirectory(prefix="agent-policy-review-candidate-verifier-") as temporary:
        environment_root = Path(temporary) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment_root)
        python = probe_python_path(environment_root)
        common = {
            "cwd": ROOT,
            "check": True,
            "capture_output": True,
            "text": True,
        }
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--no-deps",
                "--only-binary=:all:",
                "-r",
                str(VERIFIER_REQUIREMENTS),
            ],
            **common,
        )
        subprocess.run([str(python), "-m", "pip", "check"], **common)
        yield python


def verify_candidate_tree_contract(tree: Path) -> None:
    for relative in TRUSTED_REVIEW_REQUIRED_PATHS:
        if not (tree / relative).is_file():
            raise ValueError(
                f"Trusted review candidate is missing required path: {relative}"
            )

    bootstrap = (tree / "skills/agent-policy/SKILL.md").read_text(encoding="utf-8")
    bootstrap_semantics = (
        "## Trusted `pr-review` bootstrap",
        "must not perform finding analysis",
        "exact-base Git-object-backed snapshot",
        "review authority bundle",
        "No provider adapter or provider result serializer",
    )
    for semantic in bootstrap_semantics:
        if semantic not in bootstrap:
            raise ValueError(
                f"Trusted review candidate bootstrap is missing required semantics: {semantic}"
            )

    procedure = (tree / "skills/pr-review/SKILL.md").read_text(encoding="utf-8")
    if "provider-neutral" not in procedure:
        raise ValueError("Trusted review candidate procedure is not provider-neutral")
    if "Stop before merge authorization" not in procedure:
        raise ValueError("Trusted review candidate procedure does not stop before merge")
    if "references/risk-domains/index.md" not in procedure:
        raise ValueError("Trusted review candidate procedure does not bind risk-domain references")

    risk_index = (tree / RISK_DOMAIN_REFERENCE_PATHS[0]).read_text(encoding="utf-8")
    if "provider-neutral procedure-support reference" not in risk_index:
        raise ValueError("Risk-domain index does not preserve its procedure-support boundary")

    reference = (
        tree / "skills/pr-review/references/github-pull-request-review-api.md"
    ).read_text(encoding="utf-8")
    if "NOT the required output format" not in reference:
        raise ValueError("GitHub review API example lacks the non-normative output disclaimer")


def run_probe(tree: Path, revision: str, probe_python: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONPATH"] = str(tree / "src")
    environment["TRUSTED_REVIEW_CANDIDATE_REVISION"] = revision
    output = subprocess.check_output(
        [str(probe_python), "-s", "-c", TRUSTED_REVIEW_PROBE],
        cwd=tree,
        env=environment,
        text=True,
        stderr=subprocess.STDOUT,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("Trusted review candidate probe did not return an object")
    return value


def verify_probe(probe: dict[str, Any]) -> None:
    expected = {
        "validate": [],
        "render": [],
        "check": [],
        "materialize": ["REVIEW_BUNDLE_MATERIALIZED"],
        "verify": ["REVIEW_BUNDLE_VERIFIED"],
        "files": sorted(
            [
                "manifest.json",
                "procedure/SKILL.md",
                "procedure/references/github-pull-request-review-api.md",
                *RISK_DOMAIN_BUNDLE_PATHS,
                "semantic/review-policy.md",
            ]
        ),
        "manifest_bundle_format": 1,
        "manifest_has_adapter": False,
        "manifest_has_result_fields": False,
        "semantic_has_local_rule": True,
        "semantic_has_shared_review": True,
        "procedure_has_identity_refresh": True,
        "procedure_stops_before_merge": True,
    }
    if probe != expected:
        raise ValueError("Trusted review candidate end-to-end authority probe failed")


def verify_candidate(git_ref: str) -> str:
    revision = resolve_candidate_revision(git_ref)
    with extracted_revision(revision) as tree:
        verify_candidate_tree_contract(tree)
        with isolated_probe_environment() as probe_python:
            verify_probe(run_probe(tree, revision, probe_python))
    return revision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an exact Policy revision as a provider-neutral trusted-review "
            "runtime promotion candidate without changing stable release pins."
        )
    )
    parser.add_argument(
        "--git-ref",
        required=True,
        help="Git ref resolving to the exact candidate commit to verify.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        revision = verify_candidate(args.git_ref)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as exc:
        print(f"trusted review candidate verification error: {exc}", file=sys.stderr)
        return 1
    print(
        "Trusted review runtime candidate verified at "
        f"{revision}. Stable publication is intentionally unchanged; a later Skill "
        "source must embed a runtime-manifest pinning this candidate, and a later "
        "installer publication must pin that Skill source."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
