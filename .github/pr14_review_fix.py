from __future__ import annotations

import re
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} replacement count: {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"updated {label}")


adoption = Path("src/agent_policy/adoption.py")
text = adoption.read_text(encoding="utf-8")
pattern = r"def changed_adoption_sources\([\s\S]*?return tuple\(sorted\(changed\)\)\n\n\n(?=def finalized_adoption_state)"
replacement = '''def immutable_adoption_sources(
    state: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    editable_policy_paths = set(state["project_policy_files"])
    editable_policy_paths.discard(state["primary_instructions"])
    return tuple(
        sorted(
            (
                item
                for item in state["sources"]
                if item["path"] not in editable_policy_paths
            ),
            key=lambda item: item["path"],
        )
    )


def changed_adoption_sources(
    repository_root: Path,
    state: dict[str, Any],
) -> tuple[str, ...]:
    changed: list[str] = []
    for item in immutable_adoption_sources(state):
        relative = item["path"]
        lexical_name = lexical_relative_name(repository_root, relative)
        path = resolve_inside(repository_root, lexical_name, allow_missing=True)
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            changed.append(relative)
    return tuple(sorted(changed))


'''
text, count = re.subn(pattern, replacement, text, count=1)
if count != 1:
    raise RuntimeError(f"adoption source replacement count: {count}")
adoption.write_text(text, encoding="utf-8")
print("updated adoption source helper")

command = Path("src/agent_policy/commands/adopt.py")
replace_once(
    command,
    "    finalized_adoption_state,\n",
    "    finalized_adoption_state,\n    immutable_adoption_sources,\n",
    "adopt import",
)
replace_once(
    command,
    '''        live_artifacts.update(
            _snapshot_required_files(
                repository_root,
                [
                    state["primary_instructions"],
                    *state["project_policy_files"],
                ],
            )
        )
''',
    '''        guarded_source_names = {
            item["path"] for item in immutable_adoption_sources(state)
        }
        guarded_source_names.update(state["project_policy_files"])
        live_artifacts.update(
            _snapshot_required_files(
                repository_root,
                sorted(guarded_source_names),
            )
        )
''',
    "finalize guard",
)

tests = Path("tests/test_adoption_preview_finalize.py")
marker = "def test_finalized_state_cannot_preview_or_finalize_again(tmp_path: Path) -> None:\n"
addition = '''@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("CLAUDE.md", b"secondary instructions\\n"),
        (".agents/skills/manual/SKILL.md", b"# Manual skill\\n"),
    ],
)
def test_finalize_rejects_other_immutable_source_change_at_transaction_boundary(
    tmp_path: Path,
    monkeypatch,
    relative: str,
    content: bytes,
) -> None:
    (tmp_path / ".git").mkdir()
    primary = tmp_path / "AGENTS.md"
    primary.write_text("handwritten instructions\\n", encoding="utf-8")
    original_primary = primary.read_bytes()
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )
    assert diagnostics == []

    concurrent = b"concurrent immutable source change\\n"
    original_apply = adopt._apply_transaction

    def race_then_apply(*args, **kwargs):
        target.write_bytes(concurrent)
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(adopt, "_apply_transaction", race_then_apply)

    diagnostics = adopt.finalize_run(tmp_path, apply=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPT_FINALIZE"
    assert "changed during finalization" in diagnostics[0].message
    assert target.read_bytes() == concurrent
    assert primary.read_bytes() == original_primary
    assert not (tmp_path / adopt.DEFAULT_BACKUP_PATH).exists()


'''
replace_once(tests, marker, addition + marker, "immutable source tests")

replace_once(
    Path("docs/cli.md"),
    "finalizeはconfig、state、lock、preview、primary instruction、project policyを一つの入力snapshotとして扱います。temporary repositoryがそのsnapshotと一致することをrender前に検査し、最初の実書込み直前にもlive repositoryのbytesを再比較します。したがって、validationとstagingの間、またはstagingとtransactionの間にprimaryやpolicyが変更された場合もcutoverせず停止します。",
    "finalizeはconfig、state、lock、preview、adoption stateに記録された全immutable source、project policyを一つの入力snapshotとして扱います。temporary repositoryがそのsnapshotと一致することをrender前に検査し、最初の実書込み直前にもlive repositoryのbytesを再比較します。したがって、validationとstagingの間、またはstagingとtransactionの間にprimary、追加instruction、handwritten skill、policyのいずれかが変更された場合もcutoverせず停止します。",
    "CLI documentation",
)
replace_once(
    Path("docs/configuration.md"),
    "Before `adopt finalize --apply` stages or writes the cutover, it snapshots the config, adoption state, lock, preview, retained primary instruction, and every project-policy input. The temporary repository must contain exactly those bytes before rendering, and the live repository must still contain them immediately before the transaction. A concurrent change therefore aborts rather than producing instructions from an unvalidated primary or policy revision.",
    "Before `adopt finalize --apply` stages or writes the cutover, it snapshots the config, adoption state, lock, preview, every immutable source recorded in the adoption inventory, and every project-policy input. The temporary repository must contain exactly those bytes before rendering, and the live repository must still contain them immediately before the transaction. A concurrent change therefore aborts rather than finalizing against an unvalidated instruction, handwritten skill, or policy revision.",
    "configuration documentation",
)
