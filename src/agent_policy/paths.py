from __future__ import annotations

import os
from pathlib import Path


class UnsafePathError(ValueError):
    pass


FOREIGN_RESERVED_NAMESPACES = (".template-composition",)


def find_repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if start is not None:
        if (current / ".git").exists():
            return current
        raise FileNotFoundError(
            "The supplied repository path must be a Git repository root; "
            "parent repositories are not searched"
        )
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("No Git repository root found")


def find_trusted_snapshot_root(start: Path | None) -> Path:
    if start is None:
        raise FileNotFoundError("Trusted review snapshot mode requires --repository")
    root = start.expanduser().absolute()
    if root.is_symlink():
        raise ValueError(
            f"Trusted review snapshot path contains a symbolic-link component: {root}"
        )
    if not root.is_dir():
        raise FileNotFoundError("Trusted review snapshot root must be a regular directory")
    if (root / ".git").exists() or (root / ".git").is_symlink():
        raise ValueError("Trusted review snapshot root must not contain .git metadata")
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(
                f"Trusted review snapshot path contains a symbolic-link component: {current}"
            )
    return root


def _normalized_lexical_relative(root: Path, relative: str | Path) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        raise UnsafePathError(f"Absolute paths are not allowed: {relative}")
    lexical = Path(os.path.abspath(root / raw))
    try:
        return lexical.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes repository root: {relative}") from exc


def _is_at_or_below(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def resolve_inside(root: Path, relative: str | Path, *, allow_missing: bool = True) -> Path:
    root = root.resolve()
    lexical_relative = _normalized_lexical_relative(root, relative)
    for namespace in FOREIGN_RESERVED_NAMESPACES:
        if _is_at_or_below(lexical_relative, Path(namespace)):
            raise UnsafePathError(
                f"Path enters foreign reserved namespace {namespace}: {relative}"
            )

    candidate = (root / Path(relative)).resolve(strict=not allow_missing)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes repository root: {relative}") from exc
    if candidate == root / ".git" or (root / ".git") in candidate.parents:
        raise UnsafePathError(f"Writing under .git is forbidden: {relative}")

    for namespace in FOREIGN_RESERVED_NAMESPACES:
        reserved = (root / namespace).resolve(strict=False)
        if _is_at_or_below(candidate, reserved):
            raise UnsafePathError(
                f"Path resolves into foreign reserved namespace {namespace}: {relative}"
            )
    return candidate
