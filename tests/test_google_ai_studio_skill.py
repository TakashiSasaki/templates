from pathlib import Path

from agent_policy.commands import check, init, validate
from agent_policy.renderer import render_skill

SKILL_NAME = "work-in-google-ai-studio"


def test_google_ai_studio_skill_has_required_operational_boundaries() -> None:
    skill = render_skill(SKILL_NAME)["SKILL.md"]

    assert "agent-policy-generated: true" in skill
    assert "name: work-in-google-ai-studio" in skill
    assert "baseline sentinel" in skill
    assert "thin vertical slice" in skill
    assert "hard boundaries, preserved invariants, or planning boundaries" in skill
    assert "repository-local, preview-dependent, hardware-dependent" in skill
    assert "Do not guess the exported commit SHA" in skill
    assert "`NOT_OBSERVABLE`" in skill
    assert "Request GitHub export only when" in skill
    assert "external repository observer" in skill
    assert "scan3" not in skill


def test_google_ai_studio_skill_is_generated_only_when_selected(tmp_path: Path) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / ".git").mkdir()

    diagnostics = init.run(
        selected,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=["validate-agent-policy", SKILL_NAME],
    )

    assert diagnostics == []
    selected_skill = selected / f".agents/skills/{SKILL_NAME}/SKILL.md"
    assert selected_skill.is_file()
    agents = (selected / "AGENTS.md").read_text(encoding="utf-8")
    assert f"`.agents/skills/{SKILL_NAME}/SKILL.md`" in agents
    assert validate.run(selected, ".agent-policy.yml") == []
    assert check.run(selected, ".agent-policy.yml") == []

    unselected = tmp_path / "unselected"
    unselected.mkdir()
    (unselected / ".git").mkdir()

    diagnostics = init.run(
        unselected,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=["validate-agent-policy"],
    )

    assert diagnostics == []
    unselected_skill = unselected / f".agents/skills/{SKILL_NAME}/SKILL.md"
    assert not unselected_skill.exists()
    assert validate.run(unselected, ".agent-policy.yml") == []
    assert check.run(unselected, ".agent-policy.yml") == []
