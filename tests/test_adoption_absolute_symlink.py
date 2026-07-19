from pathlib import Path

from agent_policy.adoption import LOCK_PATH, inspect_repository
from agent_policy.commands import adopt


def test_prepare_rejects_absolute_secondary_source_symlink(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text(
        "handwritten instructions\n",
        encoding="utf-8",
    )
    referent = tmp_path / "instructions" / "claude.md"
    referent.parent.mkdir()
    referent.write_text("secondary instructions\n", encoding="utf-8")
    source = tmp_path / "CLAUDE.md"
    source.symlink_to(referent.resolve())

    inspection = inspect_repository(tmp_path)
    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )

    assert inspection.state == "inconsistent"
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPTION_INCONSISTENT"
    assert source.is_symlink()
    assert source.readlink() == referent.resolve()
    assert referent.read_text(encoding="utf-8") == "secondary instructions\n"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / adopt.DEFAULT_STATE_PATH).exists()
    assert not (tmp_path / LOCK_PATH).exists()
