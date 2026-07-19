from pathlib import Path

from agent_policy.commands import check, init, validate


def test_init_render_check_round_trip(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
    )
    assert diagnostics == []
    agents_path = tmp_path / "AGENTS.md"
    assert agents_path.is_file()
    agents = agents_path.read_text(encoding="utf-8")
    assert "configuration: .agent-policy.yml" in agents
    assert "Semantic configuration: `.agent-policy.yml`" in agents
    assert (
        "Pinned shared toolchain: `TakashiSasaki/agent-policy@LOCAL-DEVELOPMENT`"
        in agents
    )
    assert "Repository policy inputs:" in agents
    assert "`policy/project.md`" in agents
    assert "Generated operational skills:" in agents
    assert "`.agents/skills/validate-agent-policy/SKILL.md`" in agents
    assert (
        "_Source: `TakashiSasaki/agent-policy@LOCAL-DEVELOPMENT:"
        "policy/core/change-contract.md`"
        in agents
    )
    assert "_Source: `policy/project.md` in this repository" in agents
    assert (tmp_path / ".agent-policy.lock").is_file()
    assert (tmp_path / ".agents/skills/validate-agent-policy/SKILL.md").is_file()
    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []


def test_custom_config_path_is_discoverable_in_generated_instructions(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    config_path = "config/agent-policy.yml"

    diagnostics = init.run(
        tmp_path,
        config_path,
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
    )

    assert diagnostics == []
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert f"configuration: {config_path}" in agents
    assert f"Semantic configuration: `{config_path}`" in agents
    assert f"Change `{config_path}` or its repository policy inputs" in agents
    assert validate.run(tmp_path, config_path) == []
    assert check.run(tmp_path, config_path) == []


def test_init_refuses_handwritten_agents_file(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
    )
    assert diagnostics[0].code == "FILE_CONFLICT"
