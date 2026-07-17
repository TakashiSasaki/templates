from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    pass


def find_repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("No Git repository root found")


def resolve_inside(root: Path, relative: str | Path, *, allow_missing: bool = True) -> Path:
    root = root.resolve()
    raw = Path(relative)
    if raw.is_absolute():
        raise UnsafePathError(f"Absolute paths are not allowed: {relative}")
    candidate = (root / raw).resolve(strict=not allow_missing)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes repository root: {relative}") from exc
    if candidate == root / ".git" or (root / ".git") in candidate.parents:
        raise UnsafePathError(f"Writing under .git is forbidden: {relative}")
    return candidate
