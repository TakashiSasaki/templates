import json
from pathlib import Path

import pytest

from agent_policy.cli import parser
from agent_policy.commands import adopt, check
from agent_policy.renderer import GENERATED_MARKER
from agent_policy.yamlutil import load_yaml

POLICY_HEADER = """---
id: project.repository
severity: mandatory
overridable: true
order: 1000
---
"""


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
    stale_content = f"<!-- {GENERATED_MARKER} -->\nstale fixture\n"
    preview.write_text(stale_content, encoding="utf-8")

    assert adopt.preview_run(tmp_path) == []
    regenerated = preview.read_text(encoding="utf-8")
    assert regenerated != stale_content
    assert "stale fixture" not in regenerated
    assert GENERATED_MARKER in regenerated
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


def test_existing_project_policy_can_change_before_preview(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten instructions\n", encoding="utf-8")
    policy = tmp_path / ".agents/policies/repository.md"
    policy.parent.mkdir(parents=True)
    policy.write_text(f"{POLICY_HEADER}Initial project policy.\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        project_policy_files=[".agents/policies/repository.md"],
        verification_command="npm run verify:pr",
    )
    assert diagnostics == []

    policy.write_text(f"{POLICY_HEADER}Reviewed project policy.\n", encoding="utf-8")

    assert adopt.preview_run(tmp_path) == []
    assert not any(
        item.code == "ADOPTION_SOURCE_CHANGED"
        for item in adopt.finalize_run(tmp_path, apply=False)
    )
    preview = tmp_path / adopt.DEFAULT_PREVIEW_OUTPUT_PATH
    assert "Reviewed project policy." in preview.read_text(encoding="utf-8")


def test_legacy_prepared_state_can_preview_and_finalize(tmp_path: Path) -> None:
    _prepare_repository(tmp_path)
    state_path = tmp_path / adopt.DEFAULT_STATE_PATH
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.pop("backup_path")
    state.pop("final_output")
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert adopt.preview_run(tmp_path) == []
    diagnostics = adopt.finalize_run(tmp_path, apply=False)

    assert diagnostics
    assert not any(item.level == "error" for item in diagnostics)
    assert {item.code for item in diagnostics} == {"CREATE", "REPLACE", "UPDATE", "DELETE"}


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


def test_write_new_file_does_not_delete_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "owned-by-another-process.txt"
    destination.write_bytes(b"user data")

    with pytest.raises(FileExistsError):
        adopt._write_new_file(destination, b"transaction data")

    assert destination.read_bytes() == b"user data"


def test_transaction_preserves_raced_in_file(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "backup.txt"

    def race_then_fail(path: Path, content: bytes) -> None:
        assert path == destination
        path.write_bytes(b"raced-in user data")
        raise FileExistsError("simulated exclusive-create race")

    monkeypatch.setattr(adopt, "_write_new_file", race_then_fail)

    with pytest.raises(FileExistsError, match="simulated exclusive-create race"):
        adopt._apply_transaction(
            tmp_path,
            {"backup.txt": b"transaction data"},
            [],
            must_be_absent={"backup.txt"},
        )

    assert destination.read_bytes() == b"raced-in user data"


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


@pytest.mark.parametrize(
    "relative",
    [
        ".agent-policy.yml",
        ".agent-policy/adoption.json",
        ".agent-policy.lock",
        ".agent-policy/preview/AGENTS.md",
    ],
)
def test_finalize_rejects_live_artifact_change_during_staging(
    tmp_path: Path,
    monkeypatch,
    relative: str,
) -> None:
    original_primary = _prepare_repository(tmp_path)
    target = tmp_path / relative
    original_stage = adopt._stage_finalization

    def stage_then_race(
        repository_root: Path,
        state: dict,
        backup_name: str,
        **kwargs,
    ):
        result = original_stage(repository_root, state, backup_name, **kwargs)
        target.write_bytes(b"concurrent user change")
        return result

    monkeypatch.setattr(adopt, "_stage_finalization", stage_then_race)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "changed during finalization" in diagnostics[0].message
    assert target.read_bytes() == b"concurrent user change"
    assert (tmp_path / "AGENTS.md").read_bytes() == original_primary
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


def test_finalize_rejects_primary_change_at_transaction_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _prepare_repository(tmp_path)
    primary = tmp_path / "AGENTS.md"
    concurrent = b"concurrent primary change\n"
    original_apply = adopt._apply_transaction

    def race_then_apply(*args, **kwargs):
        primary.write_bytes(concurrent)
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(adopt, "_apply_transaction", race_then_apply)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "changed during finalization" in diagnostics[0].message
    assert primary.read_bytes() == concurrent
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


def test_finalize_rejects_policy_change_after_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original_primary = _prepare_repository(tmp_path)
    policy = tmp_path / "policy/project.md"
    concurrent = b"concurrent policy change\n"
    original_check = adopt.check_run
    calls = 0

    def check_then_race(repository_root: Path, config_path: str):
        nonlocal calls
        diagnostics = original_check(repository_root, config_path)
        calls += 1
        if calls == 1:
            policy.write_bytes(concurrent)
        return diagnostics

    monkeypatch.setattr(adopt, "check_run", check_then_race)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "input changed during finalization" in diagnostics[0].message
    assert policy.read_bytes() == concurrent
    assert (tmp_path / "AGENTS.md").read_bytes() == original_primary
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


@pytest.mark.parametrize(
    "relative",
    [
        ".agent-policy.yml",
        ".agent-policy/adoption.json",
        ".agent-policy.lock",
        ".agent-policy/preview/AGENTS.md",
    ],
)
def test_finalize_rejects_symlinked_live_artifact(
    tmp_path: Path,
    relative: str,
) -> None:
    original_primary = _prepare_repository(tmp_path)
    target = tmp_path / relative
    referent = target.with_name(f"{target.name}.referent")
    target.rename(referent)
    original_referent = referent.read_bytes()
    target.symlink_to(referent.name)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "symlinked" in diagnostics[0].message
    assert target.is_symlink()
    assert referent.read_bytes() == original_referent
    assert (tmp_path / "AGENTS.md").read_bytes() == original_primary
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


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
