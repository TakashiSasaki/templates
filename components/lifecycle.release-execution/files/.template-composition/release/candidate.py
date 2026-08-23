"""Hardened exact-candidate verification for release producers."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path, PurePosixPath

REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_GIT_CONFIG_OVERRIDES = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.ignoreStat=false",
    "-c",
    "core.sparseCheckout=false",
    "-c",
    "core.sparseCheckoutCone=false",
    "-c",
    "core.quotePath=false",
)


class CandidateError(RuntimeError):
    """Raised when the working tree cannot be trusted as the named candidate."""


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            del environment[name]
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_LITERAL_PATHSPECS"] = "1"
    return environment


def _git_prefix() -> list[str]:
    return ["git", "--no-replace-objects", *_GIT_CONFIG_OVERRIDES]


def _execute_git(
    root: Path,
    git_dir: Path,
    arguments: tuple[str, ...],
    *,
    binary: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    command = [
        *_git_prefix(),
        "--git-dir",
        str(git_dir),
        "--work-tree",
        str(root),
        *arguments,
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        env=git_environment(),
        check=False,
        capture_output=True,
        text=not binary,
    )
    if check and completed.returncode != 0:
        if binary:
            diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()
        else:
            diagnostic = completed.stderr.strip()
        raise CandidateError(
            "cannot verify candidate with Git"
            + (f": {diagnostic}" if diagnostic else "")
        )
    return completed


def _git_text(root: Path, git_dir: Path, *arguments: str) -> str:
    completed = _execute_git(root, git_dir, arguments)
    return completed.stdout.strip()


def _git_bytes(root: Path, git_dir: Path, *arguments: str) -> bytes:
    completed = _execute_git(root, git_dir, arguments, binary=True)
    return completed.stdout


def _resolve_repository(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    git_dir = root / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise CandidateError(
            "repository .git must be a regular directory; linked worktrees are not supported"
        )

    environment = git_environment()
    prefix = [*_git_prefix(), "-C", str(root)]
    absolute_git_dir = subprocess.run(
        [*prefix, "rev-parse", "--absolute-git-dir"],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if absolute_git_dir.returncode != 0:
        raise CandidateError(
            "cannot resolve repository Git directory: "
            + absolute_git_dir.stderr.strip()
        )
    resolved_git_dir = Path(absolute_git_dir.stdout.strip()).resolve()
    if resolved_git_dir != git_dir.resolve():
        raise CandidateError("Git resolved directory does not match repository .git")

    toplevel = subprocess.run(
        [*prefix, "rev-parse", "--show-toplevel"],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if toplevel.returncode != 0:
        raise CandidateError(
            "cannot resolve repository worktree: " + toplevel.stderr.strip()
        )
    if Path(toplevel.stdout.strip()).resolve() != root:
        raise CandidateError("Git resolved worktree does not match repository root")
    return root, git_dir.resolve()


def _candidate_entries(root: Path, git_dir: Path, revision: str) -> list[tuple[str, str, bytes, str]]:
    raw = _git_bytes(root, git_dir, "ls-tree", "-r", "-z", "--full-tree", revision)
    entries: list[tuple[str, str, bytes, str]] = []
    for encoded in raw.split(b"\0"):
        if not encoded:
            continue
        try:
            metadata, path_bytes = encoded.split(b"\t", 1)
            mode_bytes, kind_bytes, object_id = metadata.split(b" ", 2)
        except ValueError as exc:
            raise CandidateError("candidate tree contains malformed Git metadata") from exc
        entries.append(
            (
                mode_bytes.decode("ascii"),
                kind_bytes.decode("ascii"),
                object_id,
                os.fsdecode(path_bytes),
            )
        )
    return entries


def _assert_no_symlink_ancestors(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts:
        raise CandidateError(f"unsafe repository-relative path: {relative!r}")
    current = root
    for part in pure.parts[:-1]:
        if part in {"", ".", ".."}:
            raise CandidateError(f"unsafe repository-relative path: {relative!r}")
        current = current / part
        if current.is_symlink():
            raise CandidateError(f"repository path crosses a symlink: {relative}")
    return root.joinpath(*pure.parts)


def _verify_raw_candidate_bytes(
    root: Path,
    git_dir: Path,
    revision: str,
    *,
    allowed_modified: frozenset[str],
) -> None:
    mismatches: list[str] = []
    for mode, kind, object_id, relative in _candidate_entries(root, git_dir, revision):
        if relative in allowed_modified:
            continue
        path = _assert_no_symlink_ancestors(root, relative)
        candidate_bytes = _git_bytes(root, git_dir, "cat-file", "blob", object_id.decode("ascii"))
        if mode == "120000" and kind == "blob":
            if not path.is_symlink():
                mismatches.append(relative)
                continue
            try:
                worktree_bytes = os.fsencode(os.readlink(path))
            except OSError:
                mismatches.append(relative)
                continue
        elif mode in {"100644", "100755"} and kind == "blob":
            if path.is_symlink() or not path.is_file():
                mismatches.append(relative)
                continue
            try:
                worktree_bytes = path.read_bytes()
            except OSError:
                mismatches.append(relative)
                continue
        elif mode == "160000" or kind == "commit":
            raise CandidateError(
                f"candidate contains unsupported Git link/submodule path: {relative}"
            )
        else:
            raise CandidateError(
                f"candidate contains unsupported Git tree entry {mode} {kind}: {relative}"
            )
        if worktree_bytes != candidate_bytes:
            mismatches.append(relative)
    if mismatches:
        raise CandidateError(
            "raw tracked bytes differ from candidate revision: "
            + ", ".join(sorted(mismatches))
        )


def verify_candidate(
    root: Path,
    revision: str,
    *,
    allowed_modified: frozenset[str] = frozenset(),
) -> Path:
    if REVISION_PATTERN.fullmatch(revision) is None:
        raise CandidateError("revision must be a lowercase 40-hex Git object name")
    root, git_dir = _resolve_repository(root)

    replacement_refs = _git_text(
        root,
        git_dir,
        "for-each-ref",
        "--format=%(refname)",
        "refs/replace",
    )
    if replacement_refs:
        raise CandidateError("Git replacement objects are not permitted")

    head = _git_text(root, git_dir, "rev-parse", "--verify", "HEAD^{commit}")
    if head != revision:
        raise CandidateError("revision does not match repository HEAD")

    staged = _execute_git(
        root,
        git_dir,
        ("diff", "--cached", "--quiet", revision, "--"),
        check=False,
    )
    if staged.returncode not in {0, 1}:
        raise CandidateError("cannot inspect staged candidate changes")
    if staged.returncode == 1:
        raise CandidateError("repository has staged changes")

    _verify_raw_candidate_bytes(
        root,
        git_dir,
        revision,
        allowed_modified=allowed_modified,
    )

    untracked = _git_bytes(
        root,
        git_dir,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    paths = sorted(os.fsdecode(item) for item in untracked.split(b"\0") if item)
    if paths:
        raise CandidateError(
            "repository has untracked non-ignored files: " + ", ".join(paths)
        )
    return root


def resolve_working_directory(root: Path, relative: str) -> Path:
    if relative == ".":
        return root
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise CandidateError(f"unsafe release working directory: {relative!r}")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise CandidateError(
                f"release working directory crosses a symlink: {relative}"
            )
    if not current.is_dir():
        raise CandidateError(f"release working directory does not exist: {relative}")
    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise CandidateError(
            f"release working directory escapes repository: {relative}"
        ) from exc
    return current


def ensure_output_path(root: Path, relative: str) -> Path:
    path = _assert_no_symlink_ancestors(root, relative)
    if path.is_symlink():
        raise CandidateError(f"release output path must not be a symlink: {relative}")
    return path
