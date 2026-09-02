from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/agent-policy/scripts/review_base.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_base", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


review_base = load_script()


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def make_repository(tmp_path: Path) -> tuple[Path, str, Path]:
    repository = tmp_path / "source"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    git(repository, "config", "user.name", "Review Test")
    git(repository, "config", "user.email", "review@example.invalid")
    (repository / "policy").mkdir()
    (repository / "policy/rule.md").write_text("rule\n", encoding="utf-8")
    (repository / ".agent-policy.yml").write_text("schema_version: 2\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "base")
    revision = git(repository, "rev-parse", "HEAD")
    executable = Path(shutil.which("git") or "")
    assert executable.is_absolute()
    return repository, revision, executable


def test_materialize_and_verify_exact_base_snapshot(tmp_path: Path) -> None:
    repository, revision, executable = make_repository(tmp_path)
    snapshot = tmp_path / "trusted-base"

    result = review_base.materialize(executable, repository, revision, snapshot)

    assert result["revision"] == revision
    assert len(result["tree"]) == 40
    assert not (snapshot / ".git").exists()
    assert (snapshot / "policy/rule.md").read_text(encoding="utf-8") == "rule\n"
    assert review_base.verify(executable, repository, revision, snapshot) == result


def test_verify_rejects_snapshot_byte_drift(tmp_path: Path) -> None:
    repository, revision, executable = make_repository(tmp_path)
    snapshot = tmp_path / "trusted-base"
    review_base.materialize(executable, repository, revision, snapshot)
    (snapshot / "policy/rule.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="object mismatch"):
        review_base.verify(executable, repository, revision, snapshot)


def test_materialize_rejects_git_symlink_entries(tmp_path: Path) -> None:
    repository, _, executable = make_repository(tmp_path)
    target = repository / "policy/rule.md"
    target.unlink()
    target.symlink_to("../.agent-policy.yml")
    git(repository, "add", "policy/rule.md")
    git(repository, "commit", "-qm", "symlink")
    revision = git(repository, "rev-parse", "HEAD")

    with pytest.raises(ValueError, match="unsupported non-regular entry"):
        review_base.materialize(
            executable,
            repository,
            revision,
            tmp_path / "trusted-base-symlink",
        )
