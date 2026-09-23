from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_maintainer_source_reference import (  # noqa: E402
    CANONICAL_PLANNER_PATH,
    CANONICAL_REFERENCE_PATHS,
    CANONICAL_RULE_PATH,
    CANONICAL_SKILL_PATH,
    EXPECTED_REPOSITORY,
    IsolatedClosureEnvironment,
    SourceReferenceError,
    VerifiedSource,
    git_blob_sha,
    required_source_closure_paths,
    verify_source_reference,
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
    ).strip()


def test_all_skill_references_exist_and_canonical() -> None:
    skill_text = (ROOT / CANONICAL_SKILL_PATH).read_text(encoding="utf-8")

    # Find all references/*.md mentioned in SKILL.md
    matches = re.findall(r"references/([a-zA-Z0-9_\-]+\.md)", skill_text)
    assert len(matches) >= 5

    for filename in matches:
        ref_path = ROOT / "repository-skills" / "land-templates-stack" / "references" / filename
        assert ref_path.is_file(), f"Referenced file does not exist: {ref_path}"
        canonical_rel = f"repository-skills/land-templates-stack/references/{filename}"
        assert canonical_rel in CANONICAL_REFERENCE_PATHS, (
            f"Referenced file not in CANONICAL_REFERENCE_PATHS: {canonical_rel}"
        )


def test_closure_includes_all_progressive_references() -> None:
    skill_bytes = (ROOT / CANONICAL_SKILL_PATH).read_bytes()
    required = required_source_closure_paths(skill_bytes)

    for ref_path in CANONICAL_REFERENCE_PATHS:
        assert ref_path in required, f"Required closure missing reference path: {ref_path}"


def test_missing_reference_in_manifest_fails_closed() -> None:
    skill_bytes = (ROOT / CANONICAL_SKILL_PATH).read_bytes()
    required = required_source_closure_paths(skill_bytes)
    assert len(required) > 2

    # Omit one canonical reference from closure manifest
    omitted_ref = CANONICAL_REFERENCE_PATHS[0]
    incomplete_required = [p for p in required if p != omitted_ref]

    # Build manifest with omitted reference
    head = _git("rev-parse", "HEAD")
    manifest = {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": EXPECTED_REPOSITORY,
        "revision": head,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": git_blob_sha(skill_bytes),
        "closure": [
            {
                "path": p,
                "blob_sha": git_blob_sha((ROOT / p).read_bytes()),
            }
            for p in incomplete_required
        ],
    }

    planner_bytes = (ROOT / CANONICAL_PLANNER_PATH).read_bytes()
    with pytest.raises(SourceReferenceError, match="source closure is incomplete"):
        verify_source_reference(
            manifest,
            repo=ROOT,
            expected_planner_blob=git_blob_sha(planner_bytes),
        )


def test_poisoned_worktree_reference_cannot_shadow_closure(tmp_path: Path) -> None:
    skill_bytes = (ROOT / CANONICAL_SKILL_PATH).read_bytes()
    required = required_source_closure_paths(skill_bytes)

    closure = {p: (ROOT / p).read_bytes() for p in required}
    rule_bytes = closure[CANONICAL_RULE_PATH]

    target_ref = CANONICAL_REFERENCE_PATHS[0]
    original_ref_bytes = closure[target_ref]

    head = _git("rev-parse", "HEAD")
    verified = VerifiedSource(
        revision=head,
        skill=skill_bytes,
        rule=rule_bytes,
        skill_blob=git_blob_sha(skill_bytes),
        rule_blob=git_blob_sha(rule_bytes),
        closure=closure,
    )

    ref_file = ROOT / target_ref
    original_on_disk = ref_file.read_bytes()
    try:
        # Poison worktree reference
        ref_file.write_text("ATTACKER_CONTROLLED_POISONED_REFERENCE_CONTENT\n", encoding="utf-8")

        # Materialized isolated closure environment must yield verified bytes, not poisoned worktree
        with IsolatedClosureEnvironment(verified) as env:
            read_back = env.read_closure_bytes(target_ref)
            assert read_back == original_ref_bytes
            assert b"POISONED" not in read_back
    finally:
        ref_file.write_bytes(original_on_disk)


def test_tampered_closure_reference_fails_closed() -> None:
    skill_bytes = (ROOT / CANONICAL_SKILL_PATH).read_bytes()
    required = required_source_closure_paths(skill_bytes)
    closure = {p: (ROOT / p).read_bytes() for p in required}

    target_ref = CANONICAL_REFERENCE_PATHS[0]
    head = _git("rev-parse", "HEAD")
    verified = VerifiedSource(
        revision=head,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=git_blob_sha(skill_bytes),
        rule_blob=git_blob_sha(closure[CANONICAL_RULE_PATH]),
        closure=closure,
    )

    with IsolatedClosureEnvironment(verified) as env:
        # Tamper with file in isolated environment
        dest = env.root / target_ref
        dest.write_text("TAMPERED_IN_ROOT", encoding="utf-8")

        with pytest.raises(SourceReferenceError, match="closure bytes altered"):
            env.read_closure_file(target_ref)


def test_references_are_conditionally_discoverable() -> None:
    skill_text = (ROOT / CANONICAL_SKILL_PATH).read_text(encoding="utf-8")

    # Ensure conditional phrasing exists so references are not eagerly loaded
    assert "Do not load all references into context" in skill_text or "Consult only" in skill_text
    for ref_path in CANONICAL_REFERENCE_PATHS:
        ref_name = Path(ref_path).name
        assert ref_name in skill_text


def test_no_semantic_duplication_of_acceptance_gates() -> None:
    skill_text = (ROOT / CANONICAL_SKILL_PATH).read_text(encoding="utf-8")
    assert "pr-merge-gate" in skill_text
    assert "does not duplicate or alter their acceptance semantics" in skill_text
