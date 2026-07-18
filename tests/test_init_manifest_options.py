from pathlib import Path

from agent_policy.cli import parser
from agent_policy.commands import check, init, validate
from agent_policy.manifest import build_manifest
from agent_policy.yamlutil import load_yaml


def test_manifest_builder_supports_adoption_shaped_inputs() -> None:
    manifest = build_manifest(
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=["policy/a.md", "policy/b.md"],
        verification_command=None,
        agents_output_enabled=True,
        agents_output_path=".agent-policy/preview/AGENTS.md",
        enabled_skills=[],
    )

    assert manifest["project_policy"] == {"files": ["policy/a.md", "policy/b.md"]}
    assert "verification" not in manifest
    assert manifest["outputs"] == {
        "agents": {
            "enabled": True,
            "path": ".agent-policy/preview/AGENTS.md",
        }
    }
    assert manifest["skills"] == {"enabled": []}


def test_init_defaults_remain_compatible() -> None:
    manifest = init.proposed_manifest("LOCAL-DEVELOPMENT", ["core"])

    assert manifest["project_policy"] == {"files": ["policy/project.md"]}
    assert manifest["verification"] == {"command": "./scripts/verify.sh"}
    assert manifest["outputs"] == {"agents": {"enabled": True, "path": "AGENTS.md"}}
    assert manifest["skills"] == {"enabled": ["validate-agent-policy"]}


def test_init_applies_custom_manifest_options(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=["config/agent-policy.md"],
        verification_command=None,
        agents_output_enabled=False,
        agents_output_path=".agent-policy/preview/AGENTS.md",
        enabled_skills=[],
    )

    assert diagnostics == []
    assert (tmp_path / "config/agent-policy.md").is_file()
    assert not (tmp_path / ".agent-policy/preview/AGENTS.md").exists()
    assert not (tmp_path / ".agents/skills/validate-agent-policy/SKILL.md").exists()

    config = load_yaml(tmp_path / ".agent-policy.yml")
    assert isinstance(config, dict)
    assert config["project_policy"] == {"files": ["config/agent-policy.md"]}
    assert "verification" not in config
    assert config["outputs"] == {
        "agents": {
            "enabled": False,
            "path": ".agent-policy/preview/AGENTS.md",
        }
    }
    assert config["skills"] == {"enabled": []}
    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []


def test_init_rejects_multiple_policy_scaffolds(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=["policy/a.md", "policy/b.md"],
    )

    assert diagnostics[0].code == "INIT_PROJECT_POLICY_COUNT"


def test_cli_parses_custom_init_options() -> None:
    args = parser().parse_args(
        [
            "init",
            "--project-policy",
            "config/agent-policy.md",
            "--no-verification",
            "--agents-output-path",
            ".agent-policy/preview/AGENTS.md",
            "--disable-agents-output",
            "--skill",
            "validate-agent-policy",
        ]
    )

    assert args.project_policy == "config/agent-policy.md"
    assert args.verification_command is None
    assert args.agents_output_path == ".agent-policy/preview/AGENTS.md"
    assert args.disable_agents_output is True
    assert args.enabled_skills == ["validate-agent-policy"]
