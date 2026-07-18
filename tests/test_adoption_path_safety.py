from pathlib import Path

from agent_policy.commands import adopt


def test_inspect_rejects_instruction_symlink_escape(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (repository / "AGENTS.md").symlink_to(outside)

    diagnostics = adopt.inspect_run(repository, ".agent-policy.yml")

    assert diagnostics[0].code == "ADOPT_INSPECT"
    assert "escapes repository root" in diagnostics[0].message


def test_prepare_rejects_state_path_escape(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        state_path="../adoption.json",
    )

    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert "escapes repository root" in diagnostics[0].message
    assert not (tmp_path.parent / "adoption.json").exists()
