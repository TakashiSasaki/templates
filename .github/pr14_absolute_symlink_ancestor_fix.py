from pathlib import Path


def replace_exact(path: Path, old: str, new: str, *, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} matches, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


adoption = Path("src/agent_policy/adoption.py")
replace_exact(
    adoption,
    """def _is_absolute_symlink(path: Path) -> bool:\n    return path.is_symlink() and path.readlink().is_absolute()\n\n\n""",
    """def _is_absolute_symlink(path: Path) -> bool:\n    return path.is_symlink() and path.readlink().is_absolute()\n\n\ndef _has_absolute_symlink_component(\n    repository_root: Path,\n    target: Path,\n) -> bool:\n    repository_root = repository_root.resolve()\n    for component in (target, *target.parents):\n        if component == repository_root:\n            break\n        if _is_absolute_symlink(component):\n            return True\n    return False\n\n\n""",
)
replace_exact(
    adoption,
    "        if _is_absolute_symlink(literal):\n",
    "        if _has_absolute_symlink_component(repository_root, literal):\n",
    expected=2,
)
replace_exact(
    adoption,
    "            if _is_absolute_symlink(path):\n",
    "            if _has_absolute_symlink_component(repository_root, path):\n",
)

tests = Path("tests/test_adoption_absolute_symlink.py")
replace_exact(
    tests,
    "from pathlib import Path\n\nfrom agent_policy.adoption",
    "from pathlib import Path\n\nimport pytest\n\nfrom agent_policy.adoption",
)
addition = r'''

@pytest.mark.parametrize(
    ("link_name", "source_relative"),
    [
        (".agents", "policies/foo.md"),
        (".github", "copilot-instructions.md"),
    ],
)
def test_prepare_rejects_absolute_symlink_in_source_parent_component(
    tmp_path: Path,
    link_name: str,
    source_relative: str,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text(
        "handwritten instructions\n",
        encoding="utf-8",
    )
    referent_root = tmp_path / f"real-{link_name.removeprefix('.')}"
    source = referent_root / source_relative
    source.parent.mkdir(parents=True)
    source.write_text("secondary instructions\n", encoding="utf-8")
    link = tmp_path / link_name
    link.symlink_to(referent_root.resolve(), target_is_directory=True)

    inspection = inspect_repository(tmp_path)
    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )

    assert inspection.state == "inconsistent"
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPTION_INCONSISTENT"
    assert link.is_symlink()
    assert link.readlink() == referent_root.resolve()
    assert source.read_text(encoding="utf-8") == "secondary instructions\n"
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / adopt.DEFAULT_STATE_PATH).exists()
    assert not (tmp_path / LOCK_PATH).exists()
'''
text = tests.read_text(encoding="utf-8")
marker = "def test_prepare_rejects_absolute_symlink_in_source_parent_component("
if marker in text:
    raise RuntimeError("ancestor symlink test already exists")
tests.write_text(text.rstrip() + addition + "\n", encoding="utf-8")

docs = Path("docs/cli.md")
replace_exact(
    docs,
    "repository外を指すsymlinkも拒否します。",
    "repository外を指すsymlinkも拒否します。absolute symlinkはsource自身だけでなく、`.agents`や`.github`などlexical source pathのancestor componentに含まれる場合も`inconsistent`として拒否します。",
)
