from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import agent_policy.local_checkout as local_checkout
from agent_policy.local_checkout import (
    LocalCheckoutDiscoveryError,
    discover_local_checkout_topology,
    verify_bare_worktree_live_state,
)

DECLARATION = {
    "$schema": "../schemas/local-checkout-topology.schema.json",
    "schemaVersion": 1,
    "topologyKind": "bare-worktree",
    "workspaceRoot": ".",
    "commonGitDirectory": ".bare",
    "layout": {
        "commonRepositoryBare": True,
        "linkedWorktrees": "sibling-directories-under-workspace-root",
        "workspaceRootIsWorktree": False,
    },
    "rootGitIndirection": "optional-convenience",
}


def write_declaration(root: Path, value: dict = DECLARATION) -> None:
    (root / "contracts").mkdir()
    (root / "contracts/local-checkout-topology.json").write_text(json.dumps(value))


def git(*arguments: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True)


def make_declared_checkout(root: Path, *, branch: str = "main") -> Path:
    write_declaration(root)
    git("init", "--bare", str(root / ".bare"))
    worktree = root / branch
    git("--git-dir", str(root / ".bare"), "worktree", "add", "-b", branch, str(worktree))
    return worktree


def test_absent_contract_is_undeclared(tmp_path: Path) -> None:
    assert discover_local_checkout_topology(tmp_path).kind is None


def test_invalid_or_symlinked_declaration_fails_closed(tmp_path: Path) -> None:
    invalid = dict(DECLARATION, commonGitDirectory="../outside")
    write_declaration(tmp_path, invalid)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        discover_local_checkout_topology(tmp_path)
    assert context.value.code == "LOCAL_CHECKOUT_CONTRACT_INVALID"

    contract = tmp_path / "contracts/local-checkout-topology.json"
    contract.unlink()
    target = tmp_path / "outside.json"
    target.write_text(json.dumps(DECLARATION))
    contract.symlink_to(target)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        discover_local_checkout_topology(tmp_path)
    assert context.value.code == "LOCAL_CHECKOUT_PATH_UNSAFE"


def test_live_verification_uses_git_inventory_and_keeps_declaration_separate(
    tmp_path: Path,
) -> None:
    worktree = make_declared_checkout(tmp_path)
    topology = discover_local_checkout_topology(tmp_path)
    assert topology.is_bare_worktree
    assert not topology.linked_worktrees
    verified = verify_bare_worktree_live_state(topology, operation_path=worktree)
    assert [worktree.directory.name for worktree in verified.linked_worktrees] == ["main"]
    assert verified.branch_is_occupied("main")
    assert not verified.branch_is_occupied("other")


def test_live_layout_contradiction_fails_closed(tmp_path: Path) -> None:
    write_declaration(tmp_path)
    git("init", "--bare", str(tmp_path / ".bare"))
    outside = tmp_path / "nested" / "outside"
    outside.parent.mkdir()
    git("--git-dir", str(tmp_path / ".bare"), "worktree", "add", "-b", "main", str(outside))
    topology = discover_local_checkout_topology(tmp_path)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=outside)
    assert context.value.code == "WORKTREE_LAYOUT_CONTRADICTION"


def test_unrelated_repository_cannot_satisfy_declared_live_state(tmp_path: Path) -> None:
    declared_root = tmp_path / "declared"
    declared_root.mkdir()
    make_declared_checkout(declared_root)
    unrelated = tmp_path / "unrelated"
    git("init", str(unrelated))

    topology = discover_local_checkout_topology(declared_root)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=unrelated)
    assert context.value.code == "OPERATION_COMMON_DIRECTORY_MISMATCH"


def test_linked_worktree_from_different_common_repository_fails(tmp_path: Path) -> None:
    declared_root = tmp_path / "declared"
    declared_root.mkdir()
    make_declared_checkout(declared_root)
    other_root = tmp_path / "other"
    other_root.mkdir()
    other_worktree = make_declared_checkout(other_root)

    topology = discover_local_checkout_topology(declared_root)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=other_worktree)
    assert context.value.code == "OPERATION_COMMON_DIRECTORY_MISMATCH"


def test_valid_common_directory_does_not_authorize_unrelated_operation(
    tmp_path: Path,
) -> None:
    declared_root = tmp_path / "declared"
    declared_root.mkdir()
    make_declared_checkout(declared_root)
    unrelated = tmp_path / "unrelated"
    git("init", str(unrelated))

    topology = discover_local_checkout_topology(declared_root)
    assert topology.common_git_directory is not None
    assert subprocess.check_output(
        [
            "git",
            "--git-dir",
            str(topology.common_git_directory),
            "rev-parse",
            "--is-bare-repository",
        ],
        text=True,
    ).strip() == "true"
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=unrelated)
    assert context.value.code == "OPERATION_COMMON_DIRECTORY_MISMATCH"


def test_contradictory_worktree_inventory_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = make_declared_checkout(tmp_path)
    topology = discover_local_checkout_topology(tmp_path)
    original_git = local_checkout._git

    def contradictory_git(common: Path, *arguments: str) -> str:
        if arguments == ("worktree", "list", "--porcelain"):
            head = "0" * 40
            return (
                f"worktree {common}\nbare\n\n"
                f"worktree {worktree}\nHEAD {head}\nbranch refs/heads/main\n\n"
                f"worktree {worktree}\nHEAD {head}\ndetached\n\n"
            )
        return original_git(common, *arguments)

    monkeypatch.setattr(local_checkout, "_git", contradictory_git)
    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=worktree)
    assert context.value.code == "WORKTREE_INVENTORY_CONTRADICTION"


def test_symlinked_operation_path_fails_closed(tmp_path: Path) -> None:
    worktree = make_declared_checkout(tmp_path)
    alias = tmp_path / "operation-alias"
    alias.symlink_to(worktree, target_is_directory=True)
    topology = discover_local_checkout_topology(tmp_path)

    with pytest.raises(LocalCheckoutDiscoveryError) as context:
        verify_bare_worktree_live_state(topology, operation_path=alias)
    assert context.value.code == "OPERATION_WORKTREE_INVALID"
