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
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".agent-policy.lock").is_file()
    assert (tmp_path / ".agents/skills/validate-agent-policy/SKILL.md").is_file()
    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []


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
