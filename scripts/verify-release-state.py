#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from agent_policy.adoption import AdoptionSource, build_adoption_state
from agent_policy.identity import (
    FULL_COMMIT_SHA,
    TOOLCHAIN_BRANCH,
    TOOLCHAIN_REPOSITORY,
    immutable_toolchain_reference,
)
from agent_policy.lockfile import create_lock
from agent_policy.manifest import build_manifest
from agent_policy.renderer import render_consumer_workflow

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release/toolchain.json"
RELEASE_SCHEMA = ROOT / "schemas/toolchain-release.schema.json"
CONFIG_SCHEMA = ROOT / "schemas/agent-policy.schema.json"
ADOPTION_SCHEMA = ROOT / "schemas/adoption-state.schema.json"
BOOTSTRAP_MANIFEST = ROOT / "skills/bootstrap-agent-policy/bootstrap-manifest.yml"
WORKFLOW_TEMPLATE = ROOT / "templates/workflows/check-agent-policy.yml.j2"
REQUIRED_RELEASE_PATHS = (
    "action.yml",
    "pyproject.toml",
    "schemas/adoption-state.schema.json",
    "schemas/agent-policy.schema.json",
    "src/agent_policy/cli.py",
    "src/agent_policy/identity.py",
    "templates/workflows/check-agent-policy.yml.j2",
)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path.relative_to(ROOT)}")
    return value


def validate_schema(value: object, schema: dict[str, Any], label: str) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "root"
    raise ValueError(f"Invalid {label} at {location}: {errors[0].message}")


def git_text(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def verify_git_revision(revision: str, git_ref: str) -> None:
    source_commit = git_text("rev-parse", f"{git_ref}^{{commit}}")
    git_text("cat-file", "-e", f"{revision}^{{commit}}")
    if source_commit == revision:
        raise ValueError("Stable release revision must precede its promotion commit")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, source_commit],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"Stable release revision {revision} is not an ancestor of {git_ref}"
        )

    for path in REQUIRED_RELEASE_PATHS:
        git_text("cat-file", "-e", f"{revision}:{path}")

    identity = git_text("show", f"{revision}:src/agent_policy/identity.py")
    expected_repository = f'TOOLCHAIN_REPOSITORY = "{TOOLCHAIN_REPOSITORY}"'
    expected_branch = f'TOOLCHAIN_BRANCH = "{TOOLCHAIN_BRANCH}"'
    if expected_repository not in identity or expected_branch not in identity:
        raise ValueError("Stable revision does not identify templates:policy")


def verify_static_state() -> str:
    release = load_object(RELEASE)
    release_schema = load_object(RELEASE_SCHEMA)
    config_schema = load_object(CONFIG_SCHEMA)
    adoption_schema = load_object(ADOPTION_SCHEMA)
    bootstrap = load_object(BOOTSTRAP_MANIFEST)

    validate_schema(release, release_schema, "stable release descriptor")
    toolchain = release["toolchain"]
    if not isinstance(toolchain, dict):
        raise ValueError("Release toolchain must be an object")
    revision = toolchain.get("revision")
    if not isinstance(revision, str) or FULL_COMMIT_SHA.fullmatch(revision) is None:
        raise ValueError("Stable release revision must be a full lowercase commit SHA")
    if toolchain != immutable_toolchain_reference(revision):
        raise ValueError("Stable release toolchain identity is inconsistent")
    if bootstrap.get("toolchain") != toolchain:
        raise ValueError("Bootstrap manifest and stable release pin differ")

    contracts = release["contracts"]
    if not isinstance(contracts, dict):
        raise ValueError("Release contracts must be an object")
    if bootstrap.get("schema_version") != contracts["bootstrap_manifest"]:
        raise ValueError("Bootstrap manifest schema version differs from release state")
    if config_schema["properties"]["schema_version"]["const"] != contracts[
        "agent_policy_schema"
    ]:
        raise ValueError("Agent-policy schema version differs from release state")
    if adoption_schema["properties"]["schema_version"]["const"] != contracts[
        "adoption_state_schema"
    ]:
        raise ValueError("Adoption-state schema version differs from release state")

    config_toolchain = config_schema["properties"]["toolchain"]
    adoption_toolchain = adoption_schema["properties"]["toolchain"]
    if config_toolchain != adoption_toolchain:
        raise ValueError("Configuration and adoption schemas define different toolchains")

    manifest = build_manifest(
        toolchain_revision=revision,
        profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        agents_output_enabled=True,
        agents_output_path="AGENTS.md",
        enabled_skills=[],
    )
    validate_schema(manifest, config_schema, "generated configuration")
    if manifest["toolchain"] != toolchain:
        raise ValueError("Generated configuration does not use the stable release pin")

    adoption = build_adoption_state(
        toolchain_revision=revision,
        config_path=".agent-policy.yml",
        state_path=".agent-policy/adoption.json",
        primary_instructions="AGENTS.md",
        sources=(AdoptionSource("AGENTS.md", "a" * 64, False),),
        preview_output=".agent-policy/preview/AGENTS.md",
        selected_profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        generated_skills=[],
    )
    validate_schema(adoption, adoption_schema, "generated adoption state")
    if adoption["toolchain"] != toolchain:
        raise ValueError("Generated adoption state does not use the stable release pin")

    with tempfile.TemporaryDirectory(prefix="agent-policy-release-") as temporary:
        root = Path(temporary)
        input_path = root / "input"
        output_path = root / "output"
        input_path.write_text("input\n", encoding="utf-8")
        output_path.write_text("output\n", encoding="utf-8")
        lock = yaml.safe_load(
            create_lock(
                toolchain_repository=TOOLCHAIN_REPOSITORY,
                toolchain_revision=revision,
                inputs={"input": input_path},
                outputs={"output": output_path},
            )
        )
    if lock["lock_version"] != contracts["lock"]:
        raise ValueError("Generated lock version differs from release state")
    if lock["toolchain"] != toolchain:
        raise ValueError("Generated lock does not use the stable release pin")

    template = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    placeholder = f"uses: {TOOLCHAIN_REPOSITORY}@{{{{ revision }}}}"
    if placeholder not in template:
        raise ValueError("Consumer workflow template lost its revision placeholder")
    workflow = render_consumer_workflow(revision)
    expected_use = f"uses: {TOOLCHAIN_REPOSITORY}@{revision}"
    if expected_use not in workflow or "{{ revision }}" in workflow:
        raise ValueError("Rendered consumer workflow does not use the stable release pin")
    for mutable in ("@policy", "@main", "@master"):
        if mutable in workflow:
            raise ValueError(f"Rendered consumer workflow contains mutable reference {mutable}")

    return revision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify stable policy release and full-SHA synchronization."
    )
    parser.add_argument(
        "--git-ref",
        help="Require the stable revision to be a strict ancestor of this Git ref.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        revision = verify_static_state()
        if args.git_ref:
            verify_git_revision(revision, args.git_ref)
        print(f"Stable toolchain release is synchronized at {revision}.")
        return 0
    except (KeyError, OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release verification error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
