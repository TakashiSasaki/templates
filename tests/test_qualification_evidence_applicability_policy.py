from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
REUSE_RULE = ROOT / "policy" / "pull-request" / "reuse-valid-evidence.md"
EXACT_HEAD_RULE = ROOT / "policy" / "pull-request" / "exact-head-ci-evidence.md"
QUALIFICATION_DOCS = ROOT / "docs" / "revision-bound-qualification.md"
STAGED_DOCS = ROOT / "docs" / "staged-ci.md"


def test_core_principle_normative_prose() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8")
    exact_text = EXACT_HEAD_RULE.read_text(encoding="utf-8")
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8")

    core_statement = (
        "merge progression does not itself invalidate qualification evidence. "
        "a change to the qualified candidate state or to an evidence binding does."
    )
    assert core_statement in reuse_text.lower()
    assert core_statement in docs_text.lower()

    # Full CI rerun must not be the default
    for target in (reuse_text, docs_text):
        assert "running the full validation or ci suite is not the default" in target.lower()
        assert "selective invalidation" in target.lower()
        assert "rerun only what is required to restore qualification" in target.lower()

    # Exact head CI rule harmonizes with qualification reuse
    assert "qualification evidence whose applicability to the current candidate tree" in exact_text


def test_applicability_check_evaluates_all_twelve_dimensions() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8").lower()

    required_dimensions = [
        "qualification candidate",
        "current head",
        "effective tree identity",
        "base evolution",
        "validation-run bound identity",
        "exact-head and exact-tree bindings",
        "provider revision",
        "cross-authority revision",
        "generated or materialized state",
        "dependency, lockfile, and toolchain identity",
        "validation workflow identity",
        "repository required-check policy",
    ]
    for dim in required_dimensions:
        assert dim in reuse_text
        assert dim in docs_text or dim.replace("-", " ") in docs_text


def test_applicability_outcomes_and_fail_closed_on_unknown() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8").lower()

    for target in (reuse_text, docs_text):
        assert "applicable" in target
        assert "stale" in target
        assert "unknown" in target
        assert (
            "unknown must never be treated as applicable" in target
            or "unknown is never treated as applicable" in target
        )
        assert "fail closed" in target or "fail-closed" in target


def test_evidence_reuse_and_invalidation_conditions() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8").lower()

    # Reuse conditions
    for condition in (
        "effective candidate tree is identical",
        "no conflict resolution",
        "generated or materialized output is unchanged",
        "the validation workflow identity is unchanged",
        "provider and cross-authority revisions are unchanged",
    ):
        assert condition in reuse_text
        assert condition in docs_text or condition.replace("the ", "") in docs_text

    # Invalidation triggers
    for trigger in (
        "conflict resolution",
        "effective tree change",
        "generated or materialized output change",
        "dependency, lockfile, or toolchain change",
        "validation workflow change",
        "provider revision change",
        "cross-authority revision change",
    ):
        assert trigger in reuse_text
        assert trigger in docs_text


def test_history_only_changes_and_exact_commit_bindings() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8").lower()

    for target in (reuse_text, docs_text):
        assert "history-only" in target
        assert "solely because the commit sha changed" in target
        assert "exact commit sha" in target
        assert "tree identity alone does not waive explicit exact-commit bindings" in target or (
            "an identical tree alone does not waive explicit exact-commit bindings" in target
        )


def test_review_evidence_boundary_separation() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8")
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8")

    boundary_phrase = (
        "Reuse of qualification or CI evidence does not by itself imply reuse of review evidence. "
        "Review applicability continues to follow the repository's existing review policy"
    )
    assert boundary_phrase.lower() in reuse_text.lower()
    assert boundary_phrase.lower() in docs_text.lower()


def test_acceptance_scenarios_documented_in_docs() -> None:
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8")

    assert "Case A — Ancestor merge, tree unchanged" in docs_text
    assert "Case B — History changes, tree unchanged" in docs_text
    assert "Case C — Conflict resolution" in docs_text
    assert "Case D — Cross-authority or provider revision changes" in docs_text
    assert "Case E — Validation workflow changed" in docs_text
    assert "Case F — Repository provider requires fresh merge-result check" in docs_text


# --- Semantic Simulation and Structural Tests for Cases A-F ---

@dataclass(frozen=True)
class QualificationEvidence:
    check_id: str
    bound_head_sha: str
    bound_tree_sha: str
    bound_workflow_id: str
    bound_provider_rev: str
    bound_cross_authority_rev: str
    exact_commit_binding: bool = False
    result: str = "success"


@dataclass(frozen=True)
class CandidateState:
    head_sha: str
    tree_sha: str
    workflow_id: str
    provider_rev: str
    cross_authority_rev: str
    has_conflict_resolution: bool = False
    provider_mandates_fresh_check: bool = False
    is_known: bool = True


Applicability = Literal["applicable", "stale", "unknown"]


def evaluate_qualification_applicability(
    evidence: QualificationEvidence, candidate: CandidateState
) -> Applicability:
    if not candidate.is_known:
        return "unknown"
    if candidate.provider_mandates_fresh_check:
        return "stale"
    if candidate.has_conflict_resolution:
        return "stale"
    if candidate.tree_sha != evidence.bound_tree_sha:
        return "stale"
    if candidate.workflow_id != evidence.bound_workflow_id:
        return "stale"
    if candidate.provider_rev != evidence.bound_provider_rev:
        return "stale"
    if candidate.cross_authority_rev != evidence.bound_cross_authority_rev:
        return "stale"
    if evidence.exact_commit_binding and candidate.head_sha != evidence.bound_head_sha:
        return "stale"
    return "applicable"


def test_scenario_case_a_ancestor_merge_tree_unchanged() -> None:
    """Case A: Ancestor merge landed, next member's tree and relevant bindings unchanged."""
    evidence = QualificationEvidence(
        check_id="ci-qualification",
        bound_head_sha="sha-b-old",
        bound_tree_sha="tree-b-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
        exact_commit_binding=False,
    )
    candidate_b = CandidateState(
        head_sha="sha-b-new",
        tree_sha="tree-b-001",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
        has_conflict_resolution=False,
        provider_mandates_fresh_check=False,
    )
    outcome = evaluate_qualification_applicability(evidence, candidate_b)
    assert outcome == "applicable", "Merge progression alone must not invalidate evidence"


def test_scenario_case_b_history_changes_tree_unchanged() -> None:
    """Case B: History-only rebase, tree unchanged. Respect exact commit binding if required."""
    tree_evidence = QualificationEvidence(
        check_id="unit-tests",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-123",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
        exact_commit_binding=False,
    )
    commit_evidence = QualificationEvidence(
        check_id="commit-lint",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-123",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
        exact_commit_binding=True,
    )
    rebased_candidate = CandidateState(
        head_sha="sha-002",
        tree_sha="tree-123",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
    )
    assert evaluate_qualification_applicability(tree_evidence, rebased_candidate) == "applicable"
    assert evaluate_qualification_applicability(commit_evidence, rebased_candidate) == "stale"


def test_scenario_case_c_conflict_resolution() -> None:
    """Case C: Conflict resolution modified candidate tree."""
    evidence = QualificationEvidence(
        check_id="full-ci",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-original",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
    )
    candidate_with_conflict = CandidateState(
        head_sha="sha-resolved",
        tree_sha="tree-resolved",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
        has_conflict_resolution=True,
    )
    outcome = evaluate_qualification_applicability(evidence, candidate_with_conflict)
    assert outcome == "stale", "Tree change / conflict resolution must invalidate evidence"


def test_scenario_case_d_cross_authority_or_provider_revision_changes() -> None:
    """Case D: Provider or cross-authority revision changed."""
    evidence = QualificationEvidence(
        check_id="integration",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-v1",
    )
    candidate_new_provider = CandidateState(
        head_sha="sha-001",
        tree_sha="tree-001",
        workflow_id="wf-v1",
        provider_rev="prov-2",
        cross_authority_rev="auth-v1",
    )
    candidate_new_authority = CandidateState(
        head_sha="sha-001",
        tree_sha="tree-001",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-v2",
    )
    assert evaluate_qualification_applicability(evidence, candidate_new_provider) == "stale"
    assert evaluate_qualification_applicability(evidence, candidate_new_authority) == "stale"


def test_scenario_case_e_validation_workflow_changed() -> None:
    """Case E: Validation workflow definition changed."""
    evidence = QualificationEvidence(
        check_id="workflow-run",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
    )
    candidate_new_workflow = CandidateState(
        head_sha="sha-001",
        tree_sha="tree-001",
        workflow_id="wf-v2",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
    )
    assert evaluate_qualification_applicability(evidence, candidate_new_workflow) == "stale"


def test_scenario_case_f_provider_requires_fresh_check() -> None:
    """Case F: Repository provider branch protection mandates fresh merge-result check."""
    evidence = QualificationEvidence(
        check_id="required-check",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
    )
    candidate_platform_enforced = CandidateState(
        head_sha="sha-001",
        tree_sha="tree-001",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
        provider_mandates_fresh_check=True,
    )
    outcome = evaluate_qualification_applicability(evidence, candidate_platform_enforced)
    assert outcome == "stale", "Provider ruleset enforcement overrides policy reuse"


def test_unknown_state_fails_closed() -> None:
    """Unknown state must fail closed and never be treated as applicable."""
    evidence = QualificationEvidence(
        check_id="required-check",
        bound_head_sha="sha-001",
        bound_tree_sha="tree-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
    )
    candidate_unknown = CandidateState(
        head_sha="sha-001",
        tree_sha="tree-001",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
        is_known=False,
    )
    outcome = evaluate_qualification_applicability(evidence, candidate_unknown)
    assert outcome == "unknown"
    assert outcome != "applicable"
