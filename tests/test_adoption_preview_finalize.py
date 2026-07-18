import json
from pathlib import Path

import pytest

from agent_policy.cli import parser
from agent_policy.commands import adopt, check
from agent_policy.renderer import GENERATED_MARKER
from agent_policy.yamlutil import load_yaml


def _prepare_repository(path: Path) -> bytes:
    (path / ".git").mkdir()
    primary = path / "AGENTS.md"
    primary.write_text("handwritten instructions\n", encoding="utf-8")
    original = primary.read_bytes()
    diagnostics = adopt.prepare_run(
        path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )
    assert diagnostics == []
    return original


def test_preview_regenerates_stale_generated_output(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    preview = tmp_path / ".agent-policy/preview/AGENTS.md"
    preview.write_text(
        f"<!-- {GENERATED_MARKER} -->\nstale\n",
        encoding="utf-8",
    )

    assert adopt.preview_run(tmp_path) == []
    assert "stale" not in preview.read_text(encoding="utf-8")
    assert check.run(tmp_path, ".agent-policy.yml") == []


def test_preview_and_finalize_reject_changed_source(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("changed instructions\n", encoding="utf-8")

    preview = adopt.preview_run(tmp_path)
    finalize = adopt.finalize_run(tmp_path, apply=False)

    assert preview[0].code == "ADOPTION_SOURCE_CHANGED"
    assert preview[0].path == "AGENTS.md"
    assert finalize[0].code == "ADOPTION_SOURCE_CHANGED"
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


def test_finalize_dry_run_is_read_only(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    watched = [
        "AGENTS.md",
        ".agent-policy.yml",
        ".agent-policy/adoption.json",
        ".agent-policy/preview/AGENTS.md",
        ".agent-policy.lock",
    ]
    before = {relative: (tmp_path / relative).read_bytes() for relative in watched}

    diagnostics = adopt.finalize_run(tmp_path, apply=False)

    assert not any(item.level == "error" for item in diagnostics)
    assert {item.code for item in diagnostics} == {"CREATE", "REPLACE", "UPDATE", "DELETE"}
    assert all(
        (tmp_path / relative).read_bytes() == content
        for relative, content in before.items()
    )
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


def test_finalize_cuts_over_and_preserves_original_backup(tmp_path: Path) -> None:
    original = _prepare_repository(tmp_path)

    assert adopt.finalize_run(tmp_path, apply=True) == []

    primary = tmp_path / "AGENTS.md"
    backup = tmp_path / adopt.DEFAULT_BACKUP_PATH
    state_path = tmp_path / adopt.DEFAULT_STATE_PATH
    assert backup.read_bytes() == original
    assert GENERATED_MARKER in primary.read_text(encoding="utf-8")
    assert not (tmp_path / adopt.DEFAULT_PREVIEW_OUTPUT_PATH).exists()

    config = load_yaml(tmp_path / ".agent-policy.yml")
    assert isinstance(config, dict)
    assert config["outputs"] == {"agents": {"enabled": True, "path": "AGENTS.md"}}

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["status"] == "finalized"
    assert state["backup_path"] == adopt.DEFAULT_BACKUP_PATH
    assert state["final_output"] == "AGENTS.md"
    assert check.run(tmp_path, ".agent-policy.yml") == []


def test_finalize_rejects_stale_preview_and_backup_conflict(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    policy = tmp_path / "policy/project.md"
    policy.write_text(
        policy.read_text(encoding="utf-8") + "\nAdditional guidance.\n",
        encoding="utf-8",
    )

    diagnostics = adopt.finalize_run(tmp_path, apply=False)
    assert any(item.code == "STALE_OUTPUT" for item in diagnostics)

    assert adopt.preview_run(tmp_path) == []
    backup = tmp_path / adopt.DEFAULT_BACKUP_PATH
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("occupied\n", encoding="utf-8")
    diagnostics = adopt.finalize_run(tmp_path, apply=False)
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "already exists" in diagnostics[0].message


def test_transaction_rolls_back_partial_replacement(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "a.txt"
    first.write_bytes(b"old")
    original_write = adopt._write_atomic_bytes
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected failure")
        original_write(path, content)

    monkeypatch.setattr(adopt, "_write_atomic_bytes", fail_second)
    with pytest.raises(OSError, match="injected failure"):
        adopt._apply_transaction(
            tmp_path,
            {"a.txt": b"new-a", "b.txt": b"new-b"},
            [],
            must_be_absent=set(),
        )

    assert first.read_bytes() == b"old"
    assert not (tmp_path / "b.txt").exists()


def test_finalized_state_cannot_preview_or_finalize_again(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    assert adopt.finalize_run(tmp_path, apply=True) == []

    preview = adopt.preview_run(tmp_path)
    finalize = adopt.finalize_run(tmp_path, apply=False)

    assert preview[0].code == "ADOPT_PREVIEW"
    assert "not prepared" in preview[0].message
    assert finalize[0].code == "ADOPT_FINALIZE"
    assert "not prepared" in finalize[0].message


def test_cli_parses_preview_and_finalize() -> None:
    preview = parser().parse_args(["adopt", "preview", "--state", "state.json"])
    assert preview.adopt_command == "preview"
    assert preview.state == "state.json"

    finalize = parser().parse_args(
        [
            "adopt",
            "finalize",
            "--state",
            "state.json",
            "--backup-path",
            "backup/AGENTS.md",
            "--apply",
        ]
    )
    assert finalize.adopt_command == "finalize"
    assert finalize.state == "state.json"
    assert finalize.backup_path == "backup/AGENTS.md"
    assert finalize.apply is True
