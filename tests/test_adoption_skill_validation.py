from pathlib import Path

from agent_policy.commands import adopt


def test_prepare_rejects_invalid_skill_name_before_writing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=["../../.."],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert "Invalid generated skill name: ../../.." in diagnostics[0].message
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()
    assert not (tmp_path / ".agents/skills").exists()
