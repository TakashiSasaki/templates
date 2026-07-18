from pathlib import Path

from agent_policy.cli import parser
from agent_policy.commands import check, init, validate
from agent_policy.manifest import build_manifest
from agent_policy.yamlutil import load_yaml


def test_manifest_builder_supports_adoption_shaped_inputs() -> None:
    profiles = ["core"]
    project_policy_files = ["policy/a.md", "policy/b.md"]
    enabled_skills: list[str] = []
    manifest = build_manifest(
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=profiles,
        project_policy_files=project_policy_files,
        verification_command=None,
        agents_output_enabled=True,
        agents_output_path=".agent-policy/preview/AGENTS.md",
        enabled_skills=enabled_skills,
    )
    profiles.append("security-baseline")
    project_policy_files.clear()
    enabled_skills.append("validate-agent-policy")

    assert manifest["profiles"] == ["core"]
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
    args = parser().parse_args(["init"])

    assert manifest["project_policy"] == {"files": ["policy/project.md"]}
    assert manifest["verification"] == {"command": "./scripts/verify.sh"}
    assert manifest["outputs"] == {"agents": {"enabled": True, "path": "AGENTS.md"}}
    assert manifest["skills"] == {"enabled": ["validate-agent-policy"]}
    assert args.verification_command == "./scripts/verify.sh"


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


def test_init_rejects_config_policy_collision_before_writing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=[".agent-policy.yml"],
        enabled_skills=[],
    )

    assert diagnostics[0].code == "INIT_PATH_COLLISION"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_init_rejects_policy_skill_collision_before_writing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    skill_path = ".agents/skills/validate-agent-policy/SKILL.md"

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=[skill_path],
        enabled_skills=["validate-agent-policy"],
    )

    assert diagnostics[0].code == "INIT_PATH_COLLISION"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / skill_path).exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_init_rejects_invalid_skill_name_before_writing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=["../templates"],
    )

    assert diagnostics[0].code == "INIT_SKILL"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / "policy/project.md").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_init_rejects_parent_child_output_collision_before_writing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    agents_output = ".agents/skills/validate-agent-policy"

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        agents_output_path=agents_output,
        enabled_skills=["validate-agent-policy"],
    )

    assert diagnostics[0].code == "INIT_PATH_COLLISION"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / agents_output).exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


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
