#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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

from jsonschema import Draft202012Validator

from agent_policy.identity import (
    FULL_COMMIT_SHA,
    TOOLCHAIN_BRANCH,
    TOOLCHAIN_REPOSITORY,
    immutable_toolchain_reference,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release/toolchain.json"
RELEASE_SCHEMA = ROOT / "schemas/toolchain-release.schema.json"
RUNTIME_MANIFEST = ROOT / "skills/agent-policy/runtime-manifest.json"
CURRENT_WORKFLOW_TEMPLATE = ROOT / "templates/workflows/check-agent-policy.yml.j2"
PINNED_PROBE_REQUIREMENTS = ROOT / "release/verifier-requirements.lock"
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*$"
)
REQUIRED_RELEASE_PATHS = (
    "action.yml",
    "pyproject.toml",
    "requirements-runtime.lock",
    "schemas/adoption-state.schema.json",
    "schemas/agent-policy.schema.json",
    "src/agent_policy/adoption.py",
    "src/agent_policy/cli.py",
    "src/agent_policy/identity.py",
    "src/agent_policy/lockfile.py",
    "src/agent_policy/manifest.py",
    "src/agent_policy/renderer.py",
    "templates/workflows/check-agent-policy.yml.j2",
)
SCHEMA_V2_REQUIRED_RELEASE_PATHS = (
    "profiles/review.yml",
    "src/agent_policy/commands/check.py",
    "src/agent_policy/commands/render.py",
    "src/agent_policy/commands/validate.py",
    "src/agent_policy/config.py",
    "src/agent_policy/policy_loader.py",
    "templates/policy-context.md.j2",
)
SUPPORTED_AGENT_POLICY_SCHEMA_VERSIONS = frozenset({1, 2})
PINNED_PROBE = r"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import yaml

from agent_policy.adoption import AdoptionSource, build_adoption_state
from agent_policy.lockfile import create_lock
from agent_policy.manifest import build_manifest
from agent_policy.renderer import environment

revision = os.environ["RELEASE_REVISION"]
agent_policy_schema = int(os.environ["RELEASE_AGENT_POLICY_SCHEMA"])
manifest = build_manifest(
    toolchain_revision=revision,
    profiles=["core"],
    project_policy_files=["policy/project.md"],
    verification_command=None,
    agents_output_enabled=True,
    agents_output_path="AGENTS.md",
    enabled_skills=[],
)
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
with tempfile.TemporaryDirectory(prefix="agent-policy-pinned-release-") as temporary:
    root = Path(temporary)
    input_path = root / "input"
    output_path = root / "output"
    input_path.write_text("input\n", encoding="utf-8")
    output_path.write_text("output\n", encoding="utf-8")
    lock = yaml.safe_load(
        create_lock(
            toolchain_repository="TakashiSasaki/templates",
            toolchain_revision=revision,
            inputs={"input": input_path},
            outputs={"output": output_path},
        )
    )
workflow = environment().get_template(
    "workflows/check-agent-policy.yml.j2"
).render(revision=revision)

context_probe = None
if agent_policy_schema >= 2:
    from agent_policy.commands import check, render, validate

    policy_template = '''---
id: {rule_id}
severity: mandatory
overridable: true
order: 1000
---
# {title}

Pinned release context probe.
'''
    with tempfile.TemporaryDirectory(
        prefix="agent-policy-pinned-context-"
    ) as temporary:
        root = Path(temporary)
        (root / ".git").mkdir()
        (root / "policy").mkdir()
        (root / "policy/coding.md").write_text(
            policy_template.format(
                rule_id="project.release-probe-coding",
                title="Pinned coding context rule",
            ),
            encoding="utf-8",
        )
        (root / "policy/review.md").write_text(
            policy_template.format(
                rule_id="project.release-probe-review",
                title="Pinned review context rule",
            ),
            encoding="utf-8",
        )
        (root / ".agent-policy.yml").write_text(
            f'''schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {revision}
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files:
        - policy/coding.md
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - policy/review.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
  review:
    enabled: true
    path: .github/REVIEW_GUIDELINES.md
    context: review
    renderer: policy-context-md
skills:
  enabled: []
''',
            encoding="utf-8",
        )
        validate_diagnostics = validate.run(root, ".agent-policy.yml")
        render_diagnostics = render.run(root, ".agent-policy.yml")
        check_diagnostics = check.run(root, ".agent-policy.yml")
        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        review = (root / ".github/REVIEW_GUIDELINES.md").read_text(
            encoding="utf-8"
        )
        context_probe = {
            "validate": [item.code for item in validate_diagnostics],
            "render": [item.code for item in render_diagnostics],
            "check": [item.code for item in check_diagnostics],
            "agents_has_coding": "project.release-probe-coding" in agents,
            "agents_has_review": "project.release-probe-review" in agents,
            "agents_has_shared_review": "review.require-change-causality" in agents,
            "review_has_coding": "project.release-probe-coding" in review,
            "review_has_review": "project.release-probe-review" in review,
            "review_has_shared_review": "review.require-change-causality" in review,
            "review_has_security": "security.validate-boundaries" in review,
        }

print(
    json.dumps(
        {
            "manifest": manifest,
            "adoption": adoption,
            "lock": lock,
            "workflow": workflow,
            "context_probe": context_probe,
        }
    )
)
"""


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


def schema_contract_version(schema: dict[str, Any], label: str) -> int:
    try:
        declaration = schema["properties"]["schema_version"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{label} schema does not declare schema_version") from exc
    if not isinstance(declaration, dict):
        raise ValueError(f"{label} schema_version declaration must be an object")

    const = declaration.get("const")
    if type(const) is int and const >= 1:
        return const

    enum = declaration.get("enum")
    if isinstance(enum, list) and enum:
        if any(type(item) is not int or item < 1 for item in enum):
            raise ValueError(
                f"{label} schema_version enum must contain positive integers"
            )
        if len(enum) != len(set(enum)):
            raise ValueError(f"{label} schema_version enum must not contain duplicates")
        return max(enum)

    raise ValueError(
        f"{label} schema_version must declare a positive integer const or enum"
    )


def verify_context_probe(probe: dict[str, Any], schema_version: int) -> None:
    context_probe = probe.get("context_probe")
    if schema_version == 1:
        if context_probe is not None:
            raise ValueError("Schema-v1 pinned release unexpectedly ran context probe")
        return
    if schema_version != 2:
        raise ValueError(
            f"Release verifier does not support agent-policy schema {schema_version}"
        )
    expected = {
        "validate": [],
        "render": [],
        "check": [],
        "agents_has_coding": True,
        "agents_has_review": False,
        "agents_has_shared_review": False,
        "review_has_coding": False,
        "review_has_review": True,
        "review_has_shared_review": True,
        "review_has_security": True,
    }
    if context_probe != expected:
        raise ValueError("Pinned schema-v2 context rendering probe failed")


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
        raise ValueError("Pinned release verifier requirements must not be empty")

    normalized_names: set[str] = set()
    for requirement in requirements:
        if EXACT_REQUIREMENT.fullmatch(requirement) is None:
            raise ValueError(
                "Pinned release verifier requirements must use exact name==version pins: "
                f"{requirement}"
            )
        name = requirement.split("==", 1)[0].lower().replace("_", "-")
        if name in normalized_names:
            raise ValueError(
                f"Pinned release verifier requirement is duplicated: {requirement}"
            )
        normalized_names.add(name)
    return requirements


def probe_python_path(environment_root: Path) -> Path:
    if os.name == "nt":
        return environment_root / "Scripts/python.exe"
    return environment_root / "bin/python"


@contextmanager
def pinned_probe_environment() -> Iterator[Path]:
    locked_requirements(PINNED_PROBE_REQUIREMENTS)
    with tempfile.TemporaryDirectory(
        prefix="agent-policy-release-verifier-"
    ) as temporary:
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
                str(PINNED_PROBE_REQUIREMENTS),
            ],
            **common,
        )
        subprocess.run(
            [str(python), "-m", "pip", "check"],
            **common,
        )
        yield python


@contextmanager
def extracted_revision(revision: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="agent-policy-release-tree-") as temporary:
        root = Path(temporary)
        archive_path = root / "release.tar"
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


def run_pinned_probe(
    tree: Path,
    revision: str,
    probe_python: Path,
    agent_policy_schema: int,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONPATH"] = str(tree / "src")
    environment["RELEASE_REVISION"] = revision
    environment["RELEASE_AGENT_POLICY_SCHEMA"] = str(agent_policy_schema)
    output = subprocess.check_output(
        [str(probe_python), "-s", "-c", PINNED_PROBE],
        cwd=tree,
        env=environment,
        text=True,
        stderr=subprocess.STDOUT,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("Pinned release probe did not return an object")
    return value


def verify_git_ancestry(revision: str, git_ref: str) -> None:
    source_commit = git_text("rev-parse", f"{git_ref}^{{commit}}")
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


def verify_runtime_manifest(
    runtime_manifest: dict[str, Any],
    toolchain: dict[str, Any],
    contracts: dict[str, Any],
    stable_tree: Path,
) -> None:
    if runtime_manifest.get("schema_version") != contracts["skill_runtime_manifest"]:
        raise ValueError("Skill runtime manifest schema version differs from release state")
    if runtime_manifest.get("toolchain") != toolchain:
        raise ValueError("Skill runtime manifest and stable release pin differ")

    runtime_lock = runtime_manifest.get("runtime_lock")
    if not isinstance(runtime_lock, dict):
        raise ValueError("Skill runtime manifest runtime_lock must be an object")
    if runtime_lock.get("path") != "requirements-runtime.lock":
        raise ValueError("Skill runtime manifest runtime lock path is inconsistent")
    declared_digest = runtime_lock.get("sha256")
    if (
        not isinstance(declared_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", declared_digest) is None
    ):
        raise ValueError("Skill runtime manifest runtime lock digest must be lowercase SHA-256")
    actual_digest = hashlib.sha256(
        (stable_tree / "requirements-runtime.lock").read_bytes()
    ).hexdigest()
    if declared_digest != actual_digest:
        raise ValueError("Skill runtime manifest runtime lock digest differs from stable revision")

    project = runtime_manifest.get("project")
    if not isinstance(project, dict):
        raise ValueError("Skill runtime manifest project metadata must be an object")
    pyproject = (stable_tree / "pyproject.toml").read_text(encoding="utf-8")
    expected_name = f'name = "{project.get("distribution")}"'
    expected_version = f'version = "{project.get("version")}"'
    if expected_name not in pyproject or expected_version not in pyproject:
        raise ValueError("Skill runtime manifest project metadata differs from stable revision")
    if project.get("executable") != "agent-policy":
        raise ValueError("Skill runtime manifest executable is inconsistent")

    routes = runtime_manifest.get("routes")
    if not isinstance(routes, dict) or "finalize" in json.dumps(routes):
        raise ValueError("Skill runtime manifest routes must not expose finalization")


def verify_pinned_release(
    tree: Path,
    revision: str,
    toolchain: dict[str, Any],
    contracts: dict[str, Any],
    probe_python: Path,
) -> None:
    for relative in REQUIRED_RELEASE_PATHS:
        if not (tree / relative).is_file():
            raise ValueError(f"Stable revision is missing required path: {relative}")

    identity = (tree / "src/agent_policy/identity.py").read_text(encoding="utf-8")
    expected_repository = f'TOOLCHAIN_REPOSITORY = "{TOOLCHAIN_REPOSITORY}"'
    expected_branch = f'TOOLCHAIN_BRANCH = "{TOOLCHAIN_BRANCH}"'
    if expected_repository not in identity or expected_branch not in identity:
        raise ValueError("Stable revision does not identify templates:policy")

    config_schema = load_object(tree / "schemas/agent-policy.schema.json")
    adoption_schema = load_object(tree / "schemas/adoption-state.schema.json")
    config_version = schema_contract_version(config_schema, "agent-policy")
    adoption_version = schema_contract_version(adoption_schema, "adoption-state")
    if config_version not in SUPPORTED_AGENT_POLICY_SCHEMA_VERSIONS:
        raise ValueError(
            f"Release verifier does not support agent-policy schema {config_version}"
        )
    if config_version != contracts["agent_policy_schema"]:
        raise ValueError("Pinned agent-policy schema version differs from release state")
    if adoption_version != contracts["adoption_state_schema"]:
        raise ValueError("Pinned adoption-state schema version differs from release state")

    if config_version >= 2:
        for relative in SCHEMA_V2_REQUIRED_RELEASE_PATHS:
            if not (tree / relative).is_file():
                raise ValueError(
                    f"Schema-v2 stable revision is missing required path: {relative}"
                )

    config_toolchain = config_schema["properties"]["toolchain"]
    adoption_toolchain = adoption_schema["properties"]["toolchain"]
    if config_toolchain != adoption_toolchain:
        raise ValueError(
            "Pinned configuration and adoption schemas define different toolchains"
        )

    probe = run_pinned_probe(
        tree,
        revision,
        probe_python,
        config_version,
    )
    manifest = probe["manifest"]
    adoption = probe["adoption"]
    lock = probe["lock"]
    workflow = probe["workflow"]
    validate_schema(manifest, config_schema, "pinned generated configuration")
    validate_schema(adoption, adoption_schema, "pinned generated adoption state")
    if manifest["toolchain"] != toolchain:
        raise ValueError(
            "Pinned generated configuration does not use the stable release pin"
        )
    if adoption["toolchain"] != toolchain:
        raise ValueError(
            "Pinned generated adoption state does not use the stable release pin"
        )
    if lock["lock_version"] != contracts["lock"]:
        raise ValueError("Pinned generated lock version differs from release state")
    if lock["toolchain"] != toolchain:
        raise ValueError("Pinned generated lock does not use the stable release pin")

    expected_use = f"uses: {TOOLCHAIN_REPOSITORY}@{revision}"
    if not isinstance(workflow, str) or expected_use not in workflow:
        raise ValueError("Pinned consumer workflow does not use the stable release pin")
    if "{{ revision }}" in workflow:
        raise ValueError("Pinned consumer workflow retained its revision placeholder")
    for mutable in ("@policy", "@main", "@master"):
        if mutable in workflow:
            raise ValueError(
                f"Pinned consumer workflow contains mutable reference {mutable}"
            )

    verify_context_probe(probe, config_version)


def verify_release_state(git_ref: str | None) -> str:
    release = load_object(RELEASE)
    release_schema = load_object(RELEASE_SCHEMA)
    runtime_manifest = load_object(RUNTIME_MANIFEST)
    validate_schema(release, release_schema, "stable release descriptor")

    toolchain = release["toolchain"]
    contracts = release["contracts"]
    verifier = release["verifier"]
    if (
        not isinstance(toolchain, dict)
        or not isinstance(contracts, dict)
        or not isinstance(verifier, dict)
    ):
        raise ValueError("Release toolchain, contracts, and verifier must be objects")
    revision = toolchain.get("revision")
    if not isinstance(revision, str) or FULL_COMMIT_SHA.fullmatch(revision) is None:
        raise ValueError("Stable release revision must be a full lowercase commit SHA")
    if toolchain != immutable_toolchain_reference(revision):
        raise ValueError("Stable release toolchain identity is inconsistent")

    requirements_path = verifier.get("requirements")
    expected_requirements = PINNED_PROBE_REQUIREMENTS.relative_to(ROOT).as_posix()
    if requirements_path != expected_requirements:
        raise ValueError("Stable release verifier requirements path is inconsistent")
    locked_requirements(PINNED_PROBE_REQUIREMENTS)

    current_template = CURRENT_WORKFLOW_TEMPLATE.read_text(encoding="utf-8")
    placeholder = f"uses: {TOOLCHAIN_REPOSITORY}@{{{{ revision }}}}"
    if placeholder not in current_template:
        raise ValueError("Consumer workflow template lost its revision placeholder")

    with pinned_probe_environment() as probe_python:
        with extracted_revision(revision) as tree:
            verify_runtime_manifest(runtime_manifest, toolchain, contracts, tree)
            verify_pinned_release(
                tree,
                revision,
                toolchain,
                contracts,
                probe_python,
            )
    if git_ref:
        verify_git_ancestry(revision, git_ref)
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
        revision = verify_release_state(args.git_ref)
        print(f"Stable toolchain release is synchronized at {revision}.")
        return 0
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as exc:
        print(f"release verification error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
