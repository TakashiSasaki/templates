from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from agent_policy.adoption import AdoptionSource, build_adoption_state
from agent_policy.manifest import build_manifest
from agent_policy.renderer import render_consumer_workflow

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release/toolchain.json"
RELEASE_SCHEMA = ROOT / "schemas/toolchain-release.schema.json"
CONFIG_SCHEMA = ROOT / "schemas/agent-policy.schema.json"
ADOPTION_SCHEMA = ROOT / "schemas/adoption-state.schema.json"
BOOTSTRAP = ROOT / "skills/bootstrap-agent-policy/bootstrap-manifest.yml"
WORKFLOW = ROOT / ".github/workflows/ci.yml"


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_stable_release_descriptor_is_valid_and_matches_bootstrap() -> None:
    release = load_object(RELEASE)
    schema = load_object(RELEASE_SCHEMA)
    bootstrap = load_object(BOOTSTRAP)

    Draft202012Validator(schema).validate(release)
    assert release["toolchain"] == bootstrap["toolchain"]
    assert release["channel"] == "stable"


def test_configuration_and_adoption_schemas_share_the_toolchain_contract() -> None:
    config_schema = load_object(CONFIG_SCHEMA)
    adoption_schema = load_object(ADOPTION_SCHEMA)

    config_toolchain = config_schema["properties"]["toolchain"]  # type: ignore[index]
    adoption_toolchain = adoption_schema["properties"]["toolchain"]  # type: ignore[index]
    assert config_toolchain == adoption_toolchain


def test_generated_release_artifacts_share_one_full_sha() -> None:
    release = load_object(RELEASE)
    toolchain = release["toolchain"]
    assert isinstance(toolchain, dict)
    revision = toolchain["revision"]
    assert isinstance(revision, str)

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
    workflow = render_consumer_workflow(revision)

    assert manifest["toolchain"] == toolchain
    assert adoption["toolchain"] == toolchain
    assert f"uses: {toolchain['repository']}@{revision}" in workflow
    assert "{{ revision }}" not in workflow


def test_policy_ci_fetches_only_the_current_source_history() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "refs/pull/${PR_NUMBER}/head" in workflow
    assert "PUSH_REF: ${{ github.ref }}" in workflow
    assert 'source_ref="$PUSH_REF"' in workflow
    assert "refs/remotes/origin/policy-source" in workflow
    assert "refs/heads/main" not in workflow
    assert "refs/heads/site" not in workflow
    assert "refs/heads/webapp" not in workflow
    assert "python scripts/verify-release-state.py" in workflow


def test_release_validator_passes_static_repository_state() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify-release-state.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Stable toolchain release is synchronized" in result.stdout
