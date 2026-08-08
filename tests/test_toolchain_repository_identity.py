from __future__ import annotations

import json
from pathlib import Path

from agent_policy.adoption import AdoptionSource, build_adoption_state
from agent_policy.identity import TOOLCHAIN_BRANCH, TOOLCHAIN_REPOSITORY
from agent_policy.manifest import build_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_identity_points_to_templates_policy() -> None:
    assert TOOLCHAIN_REPOSITORY == "TakashiSasaki/templates"
    assert TOOLCHAIN_BRANCH == "policy"

    manifest = build_manifest(
        toolchain_revision="a" * 40,
        profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        agents_output_enabled=True,
        agents_output_path="AGENTS.md",
        enabled_skills=[],
    )
    assert manifest["toolchain"] == {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": "a" * 40,
    }

    adoption = build_adoption_state(
        toolchain_revision="b" * 40,
        config_path=".agent-policy.yml",
        state_path=".agent-policy/adoption.json",
        primary_instructions="AGENTS.md",
        sources=(AdoptionSource("AGENTS.md", "c" * 64, False),),
        preview_output=".agent-policy/preview/AGENTS.md",
        selected_profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        generated_skills=[],
    )
    assert adoption["toolchain"] == {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": "b" * 40,
    }


def test_schemas_and_workflow_require_templates_repository() -> None:
    config_schema = json.loads(
        (ROOT / "schemas/agent-policy.schema.json").read_text(encoding="utf-8")
    )
    adoption_schema = json.loads(
        (ROOT / "schemas/adoption-state.schema.json").read_text(encoding="utf-8")
    )
    assert config_schema["properties"]["toolchain"]["properties"]["repository"] == {
        "const": TOOLCHAIN_REPOSITORY
    }
    assert adoption_schema["properties"]["toolchain"]["properties"]["repository"] == {
        "const": TOOLCHAIN_REPOSITORY
    }

    workflow = (ROOT / "templates/workflows/check-agent-policy.yml.j2").read_text(
        encoding="utf-8"
    )
    assert f"uses: {TOOLCHAIN_REPOSITORY}@{{{{ revision }}}}" in workflow
