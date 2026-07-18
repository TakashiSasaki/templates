from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "maintain_github.py"
SPEC = importlib.util.spec_from_file_location("maintain_github", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
maintenance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = maintenance
SPEC.loader.exec_module(maintenance)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_merge_result_tree_detects_squash_merged_branch(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "branch", "-M", "main")

    git(tmp_path, "switch", "-qc", "feature")
    (tmp_path / "changed.txt").write_text("same\n", encoding="utf-8")
    git(tmp_path, "add", "changed.txt")
    git(tmp_path, "commit", "-qm", "feature")
    feature_sha = git(tmp_path, "rev-parse", "HEAD")

    git(tmp_path, "switch", "-q", "main")
    (tmp_path / "changed.txt").write_text("same\n", encoding="utf-8")
    git(tmp_path, "add", "changed.txt")
    git(tmp_path, "commit", "-qm", "squash")
    (tmp_path / "later.txt").write_text("later\n", encoding="utf-8")
    git(tmp_path, "add", "later.txt")
    git(tmp_path, "commit", "-qm", "later")
    main_sha = git(tmp_path, "rev-parse", "HEAD")

    monkeypatch.chdir(tmp_path)
    assert maintenance.merge_result_tree(main_sha, feature_sha) == maintenance.commit_tree(
        main_sha
    )


def test_merged_pr_must_match_current_branch_tip():
    pr = maintenance.PullRequest(
        number=7,
        title="Example",
        base=maintenance.PullRequestRef("owner/repo", "main", "base"),
        head=maintenance.PullRequestRef("owner/repo", "feature", "head"),
        merged_at="2026-07-18T00:00:00Z",
    )

    assert maintenance.merged_pr_matches_branch(
        pr, "owner/repo", "feature", "head"
    )
    assert not maintenance.merged_pr_matches_branch(
        pr, "owner/repo", "feature", "new-head"
    )
