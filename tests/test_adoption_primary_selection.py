from pathlib import Path

import pytest

from agent_policy.commands import adopt


@pytest.mark.parametrize(
    "source_path",
    [
        ".agents/policies/local.md",
        ".agents/skills/local/SKILL.md",
    ],
)
def test_prepare_requires_a_discovered_instruction_file(
    tmp_path: Path,
    source_path: str,
) -> None:
    (tmp_path / ".git").mkdir()
    source = tmp_path / source_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("handwritten source\n", encoding="utf-8")

    for primary in ("AGENTS.md", source_path):
        diagnostics = adopt.prepare_run(
            tmp_path,
            ".agent-policy.yml",
            apply=True,
            toolchain_revision="LOCAL-DEVELOPMENT",
            profiles=["core"],
            primary_instructions=primary,
            enabled_skills=[],
        )

        assert len(diagnostics) == 1
        assert diagnostics[0].code == "PRIMARY_INSTRUCTIONS"
        assert "discovered instruction files" in diagnostics[0].message
        assert not (tmp_path / ".agent-policy.yml").exists()
        assert not (tmp_path / ".agent-policy").exists()
        assert not (tmp_path / ".agent-policy.lock").exists()
        assert source.read_text(encoding="utf-8") == "handwritten source\n"
