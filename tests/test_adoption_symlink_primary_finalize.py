from pathlib import Path

from agent_policy.commands import adopt


def _prepare_with_symlinked_primary(path: Path) -> tuple[Path, Path, bytes]:
    (path / ".git").mkdir()
    referent = path / "CLAUDE.md"
    referent.write_text("handwritten instructions\n", encoding="utf-8")
    original = referent.read_bytes()
    primary = path / "AGENTS.md"
    primary.symlink_to(referent.name)

    diagnostics = adopt.prepare_run(
        path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        primary_instructions="AGENTS.md",
        verification_command="npm run verify:pr",
    )
    assert diagnostics == []
    return primary, referent, original


def test_finalize_rejects_symlinked_primary_without_mutating_referent(
    tmp_path: Path,
) -> None:
    primary, referent, original = _prepare_with_symlinked_primary(tmp_path)
    preview = tmp_path / adopt.DEFAULT_PREVIEW_OUTPUT_PATH

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "symlinked" in diagnostics[0].message
    assert primary.is_symlink()
    assert primary.readlink() == Path("CLAUDE.md")
    assert referent.read_bytes() == original
    assert preview.is_file()
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


def test_finalize_rejects_primary_replaced_by_symlink_before_transaction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    primary = tmp_path / "AGENTS.md"
    primary.write_text("handwritten instructions\n", encoding="utf-8")
    original = primary.read_bytes()
    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )
    assert diagnostics == []

    referent = tmp_path / "raced-primary.md"
    original_apply = adopt._apply_transaction

    def replace_then_apply(*args, **kwargs):
        primary.rename(referent)
        primary.symlink_to(referent.name)
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(adopt, "_apply_transaction", replace_then_apply)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "symlinked" in diagnostics[0].message
    assert primary.is_symlink()
    assert primary.readlink() == Path("raced-primary.md")
    assert referent.read_bytes() == original
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()
