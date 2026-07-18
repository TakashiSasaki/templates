from pathlib import Path

import pytest

from agent_policy.paths import UnsafePathError, resolve_inside


def test_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, "../outside")


def test_accepts_repository_path(tmp_path: Path) -> None:
    path = resolve_inside(tmp_path, "policy/project.md")
    assert path == tmp_path / "policy/project.md"
