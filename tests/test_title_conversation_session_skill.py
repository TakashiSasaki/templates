from pathlib import Path

from agent_policy.commands import check, init, validate
from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
TEST_REVISION = "a" * 40
SKILL_NAME = "title-conversation-session"


def test_title_conversation_session_skill_has_surface_and_authority_boundaries() -> None:
    skill = render_skill(SKILL_NAME)["SKILL.md"]

    assert "agent-policy-generated: true" in skill
    assert "name: title-conversation-session" in skill
    assert "interaction-surface procedure, not shared semantic policy" in skill
    assert "established terminal boundary" in skill
    assert "Do not imply completion, merge, deployment, review completion" in skill
    assert "authorized title-persistence mechanism" in skill
    assert "persist the raw title text" in skill
    assert "Do not add Markdown fences, backticks, or presentation-only wrappers" in skill
    assert "permits free-form presentation" in skill
    assert "fenced code blocks, or an equivalent code-output block" in skill
    assert "render the proposed title inside that code-style block" in skill
    assert "present the title as plain text instead" in skill
    assert "omit title output rather than violating a fixed response schema" in skill
    assert "Do not invent a persistence API" in skill
    assert "must not change the established work state" in skill
    assert "presentation and navigation metadata only" in skill


def test_title_conversation_session_skill_is_generated_only_when_selected(
    tmp_path: Path,
) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / ".git").mkdir()

    diagnostics = init.run(
        selected,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision=TEST_REVISION,
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
        toolchain_revision=TEST_REVISION,
        profiles=["core"],
        enabled_skills=["validate-agent-policy"],
    )

    assert diagnostics == []
    assert not (unselected / f".agents/skills/{SKILL_NAME}").exists()
    assert validate.run(unselected, ".agent-policy.yml") == []
    assert check.run(unselected, ".agent-policy.yml") == []


def test_title_behavior_is_not_registered_as_shared_policy() -> None:
    assert not (ROOT / "profiles/session-titles.yml").exists()
    assert not (ROOT / "policy/session-titles").exists()

    catalog = (ROOT / "docs/shared-policy/profiles.md").read_text(encoding="utf-8")
    assert "<!-- PROFILE: session-titles -->" not in catalog
    assert "title-conversation-session" in catalog
    assert "skills.enabled" in catalog
