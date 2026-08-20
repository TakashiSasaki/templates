from pathlib import Path

import pytest

from agent_policy.paths import UnsafePathError, resolve_inside


def test_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, "../outside")


def test_accepts_repository_path(tmp_path: Path) -> None:
    path = resolve_inside(tmp_path, "policy/project.md")
    assert path == tmp_path / "policy/project.md"


@pytest.mark.parametrize(
    "relative",
    [
        ".template-composition",
        ".template-composition/lock.json",
        "temporary/../.template-composition/staging/file",
    ],
)
def test_rejects_composition_reserved_namespace(tmp_path: Path, relative: str) -> None:
    with pytest.raises(UnsafePathError, match="foreign reserved namespace"):
        resolve_inside(tmp_path, relative)


def test_rejects_symlink_alias_into_composition_reserved_namespace(tmp_path: Path) -> None:
    reserved = tmp_path / ".template-composition"
    reserved.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(reserved, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    with pytest.raises(UnsafePathError, match="foreign reserved namespace"):
        resolve_inside(tmp_path, "alias/lock.json")
