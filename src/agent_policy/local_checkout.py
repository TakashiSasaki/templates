"""Operational ingestion and live verification of Composition local-checkout declarations."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ._local_checkout_contract import validator

LOCAL_CHECKOUT_CONTRACT_RELATIVE = validator.CONTRACT
LOCAL_CHECKOUT_SCHEMA_RELATIVE = validator.SCHEMA
CONTRACT_SOURCE_ROOT = Path(validator.__file__).parent


class LocalCheckoutDiscoveryError(RuntimeError):
    """A declared local-checkout contract is unsafe, invalid, or contradicted by live Git state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LinkedWorktree:
    directory: Path
    head: str | None
    branch: str | None


@dataclass(frozen=True)
class LocalCheckoutTopology:
    kind: str | None
    workspace_root: Path | None = None
    common_git_directory: Path | None = None
    root_git_indirection: str | None = None
    linked_worktrees: tuple[LinkedWorktree, ...] = field(default_factory=tuple)

    @property
    def is_bare_worktree(self) -> bool:
        return self.kind == "bare-worktree"

    def branch_is_occupied(self, branch: str) -> bool:
        return any(worktree.branch == branch for worktree in self.linked_worktrees)


def _safe_child(root: Path, relative: Path) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise LocalCheckoutDiscoveryError(
                "LOCAL_CHECKOUT_PATH_UNSAFE", f"path contains a symlink: {relative}"
            )
    return current


def _git(common_directory: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(common_directory), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise LocalCheckoutDiscoveryError(
            "LOCAL_CHECKOUT_GIT_FAILED", detail or "Git command failed"
        )
    return result.stdout


def discover_local_checkout_topology(root: Path) -> LocalCheckoutTopology:
    """Validate a declaration only; absence is an explicit undeclared state."""
    if root.is_symlink():
        raise LocalCheckoutDiscoveryError(
            "LOCAL_CHECKOUT_PATH_UNSAFE", "workspace root must not be a symlink"
        )
    root = root.resolve()
    contract_path = _safe_child(root, LOCAL_CHECKOUT_CONTRACT_RELATIVE)
    if not contract_path.exists():
        return LocalCheckoutTopology(kind=None)
    try:
        data = validator.load_json(root, LOCAL_CHECKOUT_CONTRACT_RELATIVE)
        schema = validator.load_json(CONTRACT_SOURCE_ROOT, LOCAL_CHECKOUT_SCHEMA_RELATIVE)
        errors = validator.validate_contract(data, schema)
    except validator.LocalCheckoutTopologyValidationError as exc:
        raise LocalCheckoutDiscoveryError("LOCAL_CHECKOUT_CONTRACT_INVALID", str(exc)) from exc
    if errors:
        raise LocalCheckoutDiscoveryError("LOCAL_CHECKOUT_CONTRACT_INVALID", "; ".join(errors))
    common = _safe_child(root, Path(data["commonGitDirectory"]))
    return LocalCheckoutTopology(
        kind=data["topologyKind"],
        workspace_root=root,
        common_git_directory=common,
        root_git_indirection=data["rootGitIndirection"],
    )


def verify_bare_worktree_live_state(topology: LocalCheckoutTopology) -> LocalCheckoutTopology:
    """Verify live Git state independently from declaration validation, without mutation."""
    if (
        not topology.is_bare_worktree
        or topology.workspace_root is None
        or topology.common_git_directory is None
    ):
        raise LocalCheckoutDiscoveryError(
            "LOCAL_CHECKOUT_UNDECLARED",
            "Bare Worktree live verification requires a declared Bare Worktree topology",
        )
    common = topology.common_git_directory
    if common.is_symlink() or not common.is_dir():
        raise LocalCheckoutDiscoveryError(
            "COMMON_GIT_DIRECTORY_INVALID", "declared common Git directory is not a safe directory"
        )
    if _git(common, "rev-parse", "--is-bare-repository").strip() != "true":
        raise LocalCheckoutDiscoveryError(
            "COMMON_GIT_DIRECTORY_INVALID", "declared common Git directory is not bare"
        )
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in _git(common, "worktree", "list", "--porcelain").splitlines():
        if not line:
            if current is not None:
                records.append(current)
                current = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current is not None:
                records.append(current)
            current = {"worktree": value}
        elif current is not None:
            current[key] = value
    if current is not None:
        records.append(current)
    worktrees: list[LinkedWorktree] = []
    for record in records:
        directory = Path(record["worktree"])
        if directory == common and "bare" in record:
            continue
        if directory == common:
            raise LocalCheckoutDiscoveryError(
                "COMMON_GIT_DIRECTORY_INVALID", "common Git directory is reported as a working tree"
            )
        if directory.parent != topology.workspace_root or directory == topology.workspace_root:
            raise LocalCheckoutDiscoveryError(
                "WORKTREE_LAYOUT_CONTRADICTION", "linked worktree is not a workspace-root sibling"
            )
        branch_ref = record.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        worktrees.append(
            LinkedWorktree(directory=directory, head=record.get("HEAD"), branch=branch)
        )
    branches = [worktree.branch for worktree in worktrees if worktree.branch is not None]
    if len(branches) != len(set(branches)):
        raise LocalCheckoutDiscoveryError(
            "BRANCH_OCCUPANCY_CONTRADICTION",
            "a local branch is checked out by multiple linked worktrees",
        )
    return LocalCheckoutTopology(
        kind=topology.kind,
        workspace_root=topology.workspace_root,
        common_git_directory=common,
        root_git_indirection=topology.root_git_indirection,
        linked_worktrees=tuple(worktrees),
    )
