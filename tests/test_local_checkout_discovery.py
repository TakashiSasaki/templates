from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

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
    write_declaration(tmp_path)
    git("init", "--bare", str(tmp_path / ".bare"))
    git(
        "--git-dir",
        str(tmp_path / ".bare"),
        "worktree",
        "add",
        "-b",
        "main",
        str(tmp_path / "main"),
    )
    topology = discover_local_checkout_topology(tmp_path)
    assert topology.is_bare_worktree
    assert not topology.linked_worktrees
    verified = verify_bare_worktree_live_state(topology)
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
        verify_bare_worktree_live_state(topology)
    assert context.value.code == "WORKTREE_LAYOUT_CONTRADICTION"
