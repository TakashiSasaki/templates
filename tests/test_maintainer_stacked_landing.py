from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts.verify_maintainer_source_reference import (
    CANONICAL_OBSERVER_LIBRARY_PATH,
    CANONICAL_OBSERVER_PATH,
    CANONICAL_PLANNER_PATH,
    CANONICAL_RULE_PATH,
    CANONICAL_SKILL_PATH,
    SourceReferenceError,
    required_source_closure_paths,
    verify_source_reference,
)

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


def _git_result(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


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
    assert "version-2" in skill
    assert "scripts/plan_review_scope.py" in skill
    assert "adaptive scope selection" in skill
    assert CANONICAL_OBSERVER_PATH in skill
    assert CANONICAL_OBSERVER_LIBRARY_PATH in required_source_closure_paths(
        skill.encode("utf-8")
    )
    assert "merge_authorization" not in skill
    assert "at most one" not in skill
    assert "targeted review coverage required" not in skill


def test_fixture_covers_required_negative_and_transition_cases() -> None:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    ids = {case["id"] for case in data["cases"]}
    assert data["schema_version"] == 1
    assert {
        "source-normal",
        "source-invalid-sha",
        "source-blob-mismatch",
        "source-missing-path",
        "source-repository-mismatch",
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
    assert all(case["facts"] and case["decision"] for case in data["cases"])
    document_cases = [case for case in data["cases"] if "source" not in case["facts"]]
    assert all(
        _evaluate_document_fixture(case["facts"]) == case["decision"]
        for case in document_cases
    )


def _evaluate_document_fixture(facts: dict) -> str:
    """Check document-only decision fixtures without mutating GitHub."""

    if "landing_skill_invokes_shared_gate" in facts:
        if (
            facts["landing_skill_invokes_shared_gate"]
            and not facts["shared_gate_calls_landing"]
            and not facts["shim_calls_landing"]
        ):
            return "continue"
        return "blocked"

    if "lower_ready" in facts:
        if (
            facts["lower_ready"]
            and facts["merge_method"] == "merge"
            and not facts["head_rewritten"]
        ):
            return "land-bottom-up"
        return "blocked"

    if "base_changed" in facts:
        return "reevaluate-affected-evidence" if facts["base_changed"] else "reuse-bound-evidence"

    if "runtime_lower" in facts:
        return "retain-runtime-coverage" if all(
            facts.get(key) is True
            for key in (
                "runtime_lower",
                "docs_upper",
                "intermediate_run_cancelled",
                "final_runtime_coverage",
            )
        ) else "blocked"

    if "tip_green" in facts:
        return "blocked" if facts["tip_green"] and not facts["lower_accepted"] else "continue"

    if "authorization" in facts:
        return (
            "human-handoff"
            if facts["implementation_complete"]
            and facts["validation_complete"]
            and not facts["authorization"]
            else "continue"
        )

    if "resumed" in facts:
        return (
            "refresh-without-duplicate"
            if facts["resumed"]
            and facts["live_refresh"]
            and not facts["duplicate_action"]
            else "blocked"
        )

    raise AssertionError(f"unclassified fixture facts: {facts}")


def test_source_fixtures_use_the_immutable_reference_boundary() -> None:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    revision = _git("rev-parse", "HEAD")
    skill_blob = _git("rev-parse", f"{revision}:{CANONICAL_SKILL_PATH}")
    rule_blob = _git("rev-parse", f"{revision}:{CANONICAL_RULE_PATH}")
    planner_blob = _git("rev-parse", f"{revision}:{CANONICAL_PLANNER_PATH}")
    source = {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": "TakashiSasaki/templates",
        "revision": revision,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": skill_blob,
        "closure": [
            {
                "path": path,
                "blob_sha": _git("rev-parse", f"{revision}:{path}"),
            }
            for path in required_source_closure_paths(SKILL.read_bytes())
        ],
    }

    with tempfile.TemporaryDirectory() as temporary:
        consumer = Path(temporary)
        shadow = consumer / CANONICAL_RULE_PATH
        shadow.parent.mkdir(parents=True)
        shadow.write_text("shadowed consumer rule\n", encoding="utf-8")
        source_cases = [case for case in data["cases"] if "source" in case["facts"]]
        for case in source_cases:
            candidate = dict(source)
            case_id = case["id"]
            if case_id == "source-invalid-sha":
                candidate["revision"] = "latest"
            elif case_id == "source-blob-mismatch":
                candidate["blob_sha"] = "0" * 40
            elif case_id == "source-missing-path":
                candidate["path"] = "repository-policy/missing.md"
            elif case_id == "source-repository-mismatch":
                candidate["repository"] = "other/repository"

            if case["decision"] == "blocked":
                try:
                    verify_source_reference(
                        candidate,
                        repo=ROOT,
                        expected_skill_blob=skill_blob,
                        expected_rule_blob=rule_blob,
                        expected_planner_blob=planner_blob,
                    )
                except SourceReferenceError:
                    continue
                raise AssertionError(f"source fixture unexpectedly accepted: {case_id}")

            verified = verify_source_reference(
                candidate,
                repo=ROOT,
                expected_skill_blob=skill_blob,
                expected_rule_blob=rule_blob,
                expected_planner_blob=planner_blob,
            )
            assert case["decision"] == "read-pinned-snapshot"
            assert verified.skill_blob == skill_blob
            assert verified.rule_blob == rule_blob
            assert verified.rule != shadow.read_bytes()


def test_source_boundary_rejects_tags_and_ignores_replacement_refs() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        _git("init", "-q", cwd=repo)
        _git("config", "user.name", "fixture", cwd=repo)
        _git("config", "user.email", "fixture@example.invalid", cwd=repo)
        skill = repo / CANONICAL_SKILL_PATH
        rule = repo / CANONICAL_RULE_PATH
        planner_path = repo / CANONICAL_PLANNER_PATH
        skill.parent.mkdir(parents=True)
        rule.parent.mkdir(parents=True)
        planner_path.parent.mkdir(parents=True)
        skill.write_text("canonical skill\n", encoding="utf-8")
        rule.write_text("canonical rule\n", encoding="utf-8")
        planner_path.write_text("canonical planner\n", encoding="utf-8")
        _git(
            "add",
            CANONICAL_SKILL_PATH,
            CANONICAL_RULE_PATH,
            CANONICAL_PLANNER_PATH,
            cwd=repo,
        )
        _git("commit", "-q", "-m", "canonical", cwd=repo)
        revision = _git("rev-parse", "HEAD", cwd=repo)
        skill_blob = _git("rev-parse", f"{revision}:{CANONICAL_SKILL_PATH}", cwd=repo)
        rule_blob = _git("rev-parse", f"{revision}:{CANONICAL_RULE_PATH}", cwd=repo)
        planner_blob = _git("rev-parse", f"{revision}:{CANONICAL_PLANNER_PATH}", cwd=repo)
        source = {
            "schema_version": 2,
            "kind": "repository-maintainer-skill-reference",
            "repository": "TakashiSasaki/templates",
            "revision": revision,
            "path": CANONICAL_SKILL_PATH,
            "blob_sha": skill_blob,
            "closure": [
                {"path": CANONICAL_RULE_PATH, "blob_sha": rule_blob},
                {"path": CANONICAL_PLANNER_PATH, "blob_sha": planner_blob},
            ],
        }

        planner_path.write_text("alternate planner\n", encoding="utf-8")
        _git("commit", "-q", "-am", "alternate planner", cwd=repo)
        alternate_revision = _git("rev-parse", "HEAD", cwd=repo)
        alternate_source = dict(source)
        alternate_source["revision"] = alternate_revision
        alternate_source["closure"] = [
            {"path": CANONICAL_RULE_PATH, "blob_sha": rule_blob},
            {
                "path": CANONICAL_PLANNER_PATH,
                "blob_sha": _git(
                    "rev-parse",
                    f"{alternate_revision}:{CANONICAL_PLANNER_PATH}",
                    cwd=repo,
                ),
            },
        ]
        try:
            verify_source_reference(
                alternate_source,
                repo=repo,
                expected_skill_blob=skill_blob,
                expected_rule_blob=rule_blob,
                expected_planner_blob=planner_blob,
            )
        except SourceReferenceError as exc:
            assert "planner blob" in str(exc)
        else:
            raise AssertionError("unadopted planner blob was accepted")

        _git("tag", "-a", "canonical-tag", "-m", "tag", revision, cwd=repo)
        tag_revision = _git("rev-parse", "refs/tags/canonical-tag", cwd=repo)
        source["revision"] = tag_revision
        try:
            verify_source_reference(
                source,
                repo=repo,
                expected_skill_blob=skill_blob,
                expected_rule_blob=rule_blob,
                expected_planner_blob=planner_blob,
            )
        except SourceReferenceError:
            pass
        else:
            raise AssertionError("annotated tag object was accepted as a commit")

        source["revision"] = revision
        skill.write_text("replacement skill\n", encoding="utf-8")
        rule.write_text("replacement rule\n", encoding="utf-8")
        planner_path.write_text("replacement planner\n", encoding="utf-8")
        _git("commit", "-q", "-am", "replacement", cwd=repo)
        replacement = _git("rev-parse", "HEAD", cwd=repo)
        _git("replace", revision, replacement, cwd=repo)
        verified = verify_source_reference(
            source,
            repo=repo,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )
        assert verified.skill == b"canonical skill\n"
        assert verified.rule == b"canonical rule\n"


def test_source_boundary_rejects_missing_or_tampered_closure() -> None:
    revision = _git("rev-parse", "HEAD")
    skill_blob = _git("rev-parse", f"{revision}:{CANONICAL_SKILL_PATH}")
    rule_blob = _git("rev-parse", f"{revision}:{CANONICAL_RULE_PATH}")
    planner_blob = _git("rev-parse", f"{revision}:{CANONICAL_PLANNER_PATH}")
    source = {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": "TakashiSasaki/templates",
        "revision": revision,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": skill_blob,
        "closure": [{"path": CANONICAL_RULE_PATH, "blob_sha": rule_blob}],
    }
    try:
        verify_source_reference(source, repo=ROOT, expected_planner_blob=planner_blob)
    except SourceReferenceError as exc:
        assert "closure" in str(exc)
    else:
        raise AssertionError("incomplete source closure was accepted")

    source["closure"] = [
        {
            "path": path,
            "blob_sha": _git("rev-parse", f"{revision}:{path}"),
        }
        for path in required_source_closure_paths(SKILL.read_bytes())
    ]
    next(
        item for item in source["closure"] if item["path"] == CANONICAL_PLANNER_PATH
    )["blob_sha"] = "0" * 40
    try:
        verify_source_reference(source, repo=ROOT, expected_planner_blob=planner_blob)
    except SourceReferenceError as exc:
        assert "closure blob" in str(exc)
    else:
        raise AssertionError("tampered source closure was accepted")


def test_observer_skill_requires_observer_source_closure() -> None:
    revision = _git("rev-parse", "HEAD")
    skill_blob = _git("rev-parse", f"{revision}:{CANONICAL_SKILL_PATH}")
    rule_blob = _git("rev-parse", f"{revision}:{CANONICAL_RULE_PATH}")
    planner_blob = _git("rev-parse", f"{revision}:{CANONICAL_PLANNER_PATH}")
    source = {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": "TakashiSasaki/templates",
        "revision": revision,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": skill_blob,
        "closure": [
            {"path": CANONICAL_RULE_PATH, "blob_sha": rule_blob},
            {"path": CANONICAL_PLANNER_PATH, "blob_sha": planner_blob},
        ],
    }

    with pytest.raises(SourceReferenceError, match="source closure is incomplete"):
        verify_source_reference(
            source,
            repo=ROOT,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )


def test_source_boundary_rejects_legacy_schema_one() -> None:
    try:
        verify_source_reference({"schema_version": 1}, repo=ROOT)
    except SourceReferenceError as exc:
        assert "schema version 2" in str(exc)
    else:
        raise AssertionError("legacy source schema was accepted")


def test_canonical_source_object_is_resolvable_from_the_current_snapshot() -> None:
    revision = _git("rev-parse", "HEAD")
    assert FULL_SHA.fullmatch(revision)
    for path in (
        "repository-policy/stacked-pr-landing.md",
        "repository-skills/land-templates-stack/SKILL.md",
        "repository-skills/land-templates-stack/scripts/plan_review_scope.py",
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
        ancestry = _git_result("merge-base", "--is-ancestor", bottom_head, "HEAD", cwd=repo)
        assert ancestry.returncode == 0, ancestry.stderr


def test_shared_profile_does_not_receive_repository_specific_rule() -> None:
    profile_text = (ROOT / "profiles" / "pull-request.yml").read_text(encoding="utf-8")
    assert "stacked-pr-landing.md" not in profile_text
