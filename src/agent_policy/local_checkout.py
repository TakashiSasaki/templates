"""Operational ingestion and live verification of Composition local-checkout declarations."""

from __future__ import annotations

import os
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


def _git_at(operation_path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(operation_path), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise LocalCheckoutDiscoveryError(
            "OPERATION_WORKTREE_INVALID",
            detail or "operation path is not in a Git worktree",
        )
    return result.stdout


def _resolve_safe_directory(path: Path, *, code: str, description: str) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise LocalCheckoutDiscoveryError(code, f"{description} contains a symlink: {path}")
    if not absolute.is_dir():
        raise LocalCheckoutDiscoveryError(code, f"{description} is not a directory: {path}")
    return absolute.resolve(strict=True)


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


def verify_bare_worktree_live_state(
    topology: LocalCheckoutTopology, *, operation_path: Path
) -> LocalCheckoutTopology:
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
    common = _resolve_safe_directory(
        topology.common_git_directory,
        code="COMMON_GIT_DIRECTORY_INVALID",
        description="declared common Git directory",
    )
    if _git(common, "rev-parse", "--is-bare-repository").strip() != "true":
        raise LocalCheckoutDiscoveryError(
            "COMMON_GIT_DIRECTORY_INVALID", "declared common Git directory is not bare"
        )

    operation = _resolve_safe_directory(
        operation_path,
        code="OPERATION_WORKTREE_INVALID",
        description="operation path",
    )
    operation_root = _resolve_safe_directory(
        Path(_git_at(operation, "rev-parse", "--show-toplevel").strip()),
        code="OPERATION_WORKTREE_INVALID",
        description="operation worktree root",
    )
    operation_common = _resolve_safe_directory(
        Path(
            _git_at(
                operation,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ).strip()
        ),
        code="OPERATION_WORKTREE_INVALID",
        description="operation Git common directory",
    )
    if operation_common != common:
        raise LocalCheckoutDiscoveryError(
            "OPERATION_COMMON_DIRECTORY_MISMATCH",
            "operation worktree does not belong to the declared common Git directory",
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
        if not record.get("worktree"):
            raise LocalCheckoutDiscoveryError(
                "WORKTREE_INVENTORY_CONTRADICTION",
                "Git worktree inventory contains a record without a worktree path",
            )
        directory = _resolve_safe_directory(
            Path(record["worktree"]),
            code="WORKTREE_INVENTORY_CONTRADICTION",
            description="inventory worktree path",
        )
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
        inventory_root = _resolve_safe_directory(
            Path(_git_at(directory, "rev-parse", "--show-toplevel").strip()),
            code="WORKTREE_INVENTORY_CONTRADICTION",
            description="inventory worktree root",
        )
        inventory_common = _resolve_safe_directory(
            Path(
                _git_at(
                    directory,
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                ).strip()
            ),
            code="WORKTREE_INVENTORY_CONTRADICTION",
            description="inventory Git common directory",
        )
        if inventory_root != directory or inventory_common != common:
            raise LocalCheckoutDiscoveryError(
                "WORKTREE_INVENTORY_CONTRADICTION",
                "linked worktree inventory disagrees with live Git state",
            )
        branch_ref = record.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        worktrees.append(
            LinkedWorktree(directory=directory, head=record.get("HEAD"), branch=branch)
        )
    directories = [worktree.directory for worktree in worktrees]
    if len(directories) != len(set(directories)):
        raise LocalCheckoutDiscoveryError(
            "WORKTREE_INVENTORY_CONTRADICTION",
            "Git worktree inventory contains a duplicate worktree path",
        )
    if directories.count(operation_root) != 1:
        raise LocalCheckoutDiscoveryError(
            "OPERATION_WORKTREE_NOT_IN_INVENTORY",
            "operation worktree is not represented exactly once in the declared "
            "repository inventory",
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
