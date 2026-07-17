from pathlib import Path
import pytest

from agent_policy.paths import UnsafePathError, resolve_inside


def test_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, "../outside")


def test_rejects_git_path(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, ".git/config")
