from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "repository-policy" / "stacked-pr-landing.md"
SKILL = ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md"
CASES = ROOT / "tests" / "fixtures" / "maintainer-stacked-landing" / "cases.json"
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def _git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canonical_rule_and_skill_are_present_and_separated() -> None:
    rule = _read(RULE)
    skill = _read(SKILL)

    assert "# Maintainer stacked-PR landing rules" in rule
    assert "# Land the templates maintenance stack" in skill
    assert "repository-policy/stacked-pr-landing.md" in skill
    assert "skills/pr-merge-gate/SKILL.md" in skill
    assert "does not copy their acceptance semantics" in skill
    assert "does not authorize a merge" in skill


def test_fixture_covers_required_negative_and_transition_cases() -> None:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    ids = {case["id"] for case in data["cases"]}
    assert data["schema_version"] == 1
    assert {
        "source-normal",
        "source-invalid-sha",
        "source-blob-mismatch",
        "source-missing-path",
        "source-closure-shadowing",
        "no-circular-invocation",
        "bottom-up-history",
        "evidence-binding-change",
        "runtime-docs-cumulative",
        "tip-not-prefix",
        "human-handoff",
        "resume-idempotence",
    } <= ids
    assert all(case["condition"] and case["expected"] for case in data["cases"])


def test_canonical_source_object_is_resolvable_from_the_current_snapshot() -> None:
    revision = _git("rev-parse", "HEAD")
    assert FULL_SHA.fullmatch(revision)
    for path in (
        "repository-policy/stacked-pr-landing.md",
        "repository-skills/land-templates-stack/SKILL.md",
    ):
        object_id = _git("rev-parse", f"{revision}:{path}")
        assert FULL_SHA.fullmatch(object_id)
        assert _git("cat-file", "-e", f"{revision}:{path}") == ""


def test_invalid_source_identities_fail_closed_without_mutable_fallback() -> None:
    revision = _git("rev-parse", "HEAD")
    rule_blob = _git("rev-parse", f"{revision}:repository-policy/stacked-pr-landing.md")
    assert not FULL_SHA.fullmatch(revision[:12])
    assert not FULL_SHA.fullmatch("latest")
    assert rule_blob != "0" * 40
    missing = subprocess.run(
        ["git", "rev-parse", f"{revision}:repository-policy/does-not-exist.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0
    assert (
        _git("rev-parse", f"{revision}:repository-policy/stacked-pr-landing.md")
        != "0" * 40
    )


def test_skill_uses_snapshot_closure_and_has_no_circular_landing_call() -> None:
    skill = _read(SKILL)
    assert "git show <revision>:repository-policy/stacked-pr-landing.md" in skill
    assert "consumer's same-named `repository-policy/` file" in skill
    assert "invoke the pinned shared `pr-merge-gate`" in skill
    assert "must not call itself" in skill
    assert "local shim must not call the local" in skill


def test_rule_preserves_prefix_and_cumulative_evidence_distinctions() -> None:
    rule = " ".join(_read(RULE).lower().split())
    skill = " ".join(_read(SKILL).lower().split())
    corpus = f"{rule}\n{skill}"
    for phrase in (
        "a tip-only approval does not establish cumulative coverage",
        "final tip's success does not prove",
        "runtime-changing lower member",
        "docs-only member",
        "newly started workflow run does not inherit",
        "runs started and completed",
    ):
        assert phrase in corpus


def test_local_temporary_git_history_preserves_bottom_up_merge_and_upper_head() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        _git("init", "-q", cwd=repo)
        _git("config", "user.name", "fixture", cwd=repo)
        _git("config", "user.email", "fixture@example.invalid", cwd=repo)
        (repo / "state.txt").write_text("base\n", encoding="utf-8")
        _git("add", "state.txt", cwd=repo)
        _git("commit", "-q", "-m", "base", cwd=repo)
        _git("branch", "authority", cwd=repo)
        _git("switch", "-q", "-c", "bottom", cwd=repo)
        (repo / "state.txt").write_text("base\nbottom\n", encoding="utf-8")
        _git("commit", "-q", "-am", "bottom", cwd=repo)
        bottom_head = _git("rev-parse", "HEAD", cwd=repo)
        _git("switch", "-q", "-c", "upper", cwd=repo)
        (repo / "upper.txt").write_text("upper\n", encoding="utf-8")
        _git("add", "upper.txt", cwd=repo)
        _git("commit", "-q", "-m", "upper", cwd=repo)
        upper_head = _git("rev-parse", "HEAD", cwd=repo)
        _git("switch", "-q", "authority", cwd=repo)
        _git("merge", "--no-ff", "--no-edit", "bottom", cwd=repo)
        assert _git("rev-parse", "upper", cwd=repo) == upper_head
        assert _git("merge-base", "--is-ancestor", bottom_head, "HEAD", cwd=repo, check=False) == ""


def test_shared_profile_does_not_receive_repository_specific_rule() -> None:
    profile_text = (ROOT / "profiles" / "pull-request.yml").read_text(encoding="utf-8")
    assert "stacked-pr-landing.md" not in profile_text
