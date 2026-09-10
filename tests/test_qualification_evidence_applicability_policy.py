from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
REUSE_RULE = ROOT / "policy" / "pull-request" / "reuse-valid-evidence.md"
EXACT_HEAD_RULE = ROOT / "policy" / "pull-request" / "exact-head-ci-evidence.md"
STAGED_POLICY = ROOT / "policy" / "pull-request" / "staged-ci-and-preflight.md"
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

    for target in (reuse_text, docs_text):
        assert "running the full validation or ci suite is not the default" in target.lower()
        assert "selective invalidation" in target.lower()
        assert "rerun only what is required to restore qualification" in target.lower()

    assert "tree-and-context-bound" in exact_text
    assert "exact-revision-bound" in exact_text
    assert "ordinary CI success" in exact_text
    assert "unknown" in exact_text


def test_binding_classification_reconciles_head_movement_rules() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    exact_text = EXACT_HEAD_RULE.read_text(encoding="utf-8").lower()
    staged_policy = STAGED_POLICY.read_text(encoding="utf-8").lower()

    for target in (reuse_text, exact_text, staged_policy):
        assert "tree-and-context-bound" in target
        assert "exact-revision-bound" in target

    assert "ordinary successful ci result is never inferred" in reuse_text
    assert "ordinary ci success with no explicit binding classification is **unknown**" in exact_text
    assert "head-sha-only change" in staged_policy
    assert "unclassified/unknown evidence stale" in staged_policy
    assert "proposed-head change makes prior exact-head review stale" in staged_policy


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

    for condition in (
        "effective candidate tree is identical",
        "no conflict resolution",
        "generated or materialized output is unchanged",
        "the validation workflow identity is unchanged",
        "provider and cross-authority revisions are unchanged",
    ):
        assert condition in reuse_text
        assert condition in docs_text or condition.replace("the ", "") in docs_text

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

    assert "validation environment identity is unchanged" in reuse_text
    assert "validation environment change" in reuse_text


def test_history_only_changes_and_exact_commit_bindings() -> None:
    reuse_text = REUSE_RULE.read_text(encoding="utf-8").lower()
    docs_text = QUALIFICATION_DOCS.read_text(encoding="utf-8").lower()

    for target in (reuse_text, docs_text):
        assert "history-only" in target
        assert "solely because the commit sha changed" in target
        assert "exact commit sha" in target
        assert "tree identity alone does not waive explicit exact-commit bindings" in target or (
            "an identical tree alone does not waive explicit exact-commit" in target
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


BindingClass = Literal["tree-and-context", "exact-revision", "unknown"]
Applicability = Literal["applicable", "stale", "unknown"]


@dataclass(frozen=True)
class QualificationEvidence:
    check_id: str
    bound_head_sha: str
    bound_tree_sha: str
    bound_workflow_id: str
    bound_provider_rev: str
    bound_cross_authority_rev: str
    bound_generated_state_id: str = "generated-v1"
    bound_dependency_id: str = "deps-v1"
    bound_lockfile_id: str = "lock-v1"
    bound_toolchain_id: str = "toolchain-v1"
    bound_validation_environment_id: str = "env-v1"
    binding_class: BindingClass = "tree-and-context"
    result: str = "success"


@dataclass(frozen=True)
class CandidateState:
    head_sha: str
    tree_sha: str
    workflow_id: str
    provider_rev: str
    cross_authority_rev: str
    generated_state_id: str = "generated-v1"
    dependency_id: str = "deps-v1"
    lockfile_id: str = "lock-v1"
    toolchain_id: str = "toolchain-v1"
    validation_environment_id: str = "env-v1"
    has_conflict_resolution: bool = False
    provider_mandates_fresh_check: bool = False
    is_known: bool = True


def evaluate_qualification_applicability(
    evidence: QualificationEvidence, candidate: CandidateState
) -> Applicability:
    if not candidate.is_known or evidence.binding_class == "unknown":
        return "unknown"
    if candidate.provider_mandates_fresh_check or candidate.has_conflict_resolution:
        return "stale"
    if candidate.tree_sha != evidence.bound_tree_sha:
        return "stale"
    if candidate.generated_state_id != evidence.bound_generated_state_id:
        return "stale"
    if candidate.dependency_id != evidence.bound_dependency_id:
        return "stale"
    if candidate.lockfile_id != evidence.bound_lockfile_id:
        return "stale"
    if candidate.toolchain_id != evidence.bound_toolchain_id:
        return "stale"
    if candidate.validation_environment_id != evidence.bound_validation_environment_id:
        return "stale"
    if candidate.workflow_id != evidence.bound_workflow_id:
        return "stale"
    if candidate.provider_rev != evidence.bound_provider_rev:
        return "stale"
    if candidate.cross_authority_rev != evidence.bound_cross_authority_rev:
        return "stale"
    if evidence.binding_class == "exact-revision" and candidate.head_sha != evidence.bound_head_sha:
        return "stale"
    return "applicable"


def base_evidence(**overrides: object) -> QualificationEvidence:
    evidence = QualificationEvidence(
        check_id="qualification",
        bound_head_sha="sha-old",
        bound_tree_sha="tree-001",
        bound_workflow_id="wf-v1",
        bound_provider_rev="prov-1",
        bound_cross_authority_rev="auth-1",
    )
    return replace(evidence, **overrides)


def base_candidate(**overrides: object) -> CandidateState:
    candidate = CandidateState(
        head_sha="sha-new",
        tree_sha="tree-001",
        workflow_id="wf-v1",
        provider_rev="prov-1",
        cross_authority_rev="auth-1",
    )
    return replace(candidate, **overrides)


def test_scenario_case_a_ancestor_merge_tree_unchanged() -> None:
    evidence = base_evidence(binding_class="tree-and-context")
    candidate = base_candidate()
    assert evaluate_qualification_applicability(evidence, candidate) == "applicable"


def test_scenario_case_b_history_changes_tree_unchanged() -> None:
    tree_evidence = base_evidence(binding_class="tree-and-context")
    exact_revision_evidence = base_evidence(binding_class="exact-revision")
    unknown_binding_evidence = base_evidence(binding_class="unknown")
    candidate = base_candidate()

    assert evaluate_qualification_applicability(tree_evidence, candidate) == "applicable"
    assert evaluate_qualification_applicability(exact_revision_evidence, candidate) == "stale"
    assert evaluate_qualification_applicability(unknown_binding_evidence, candidate) == "unknown"


def test_scenario_case_c_conflict_resolution() -> None:
    evidence = base_evidence()
    candidate = base_candidate(
        head_sha="sha-resolved",
        tree_sha="tree-resolved",
        has_conflict_resolution=True,
    )
    assert evaluate_qualification_applicability(evidence, candidate) == "stale"


def test_scenario_case_d_cross_authority_or_provider_revision_changes() -> None:
    evidence = base_evidence()
    assert evaluate_qualification_applicability(
        evidence, base_candidate(provider_rev="prov-2")
    ) == "stale"
    assert evaluate_qualification_applicability(
        evidence, base_candidate(cross_authority_rev="auth-2")
    ) == "stale"


def test_scenario_case_e_validation_workflow_changed() -> None:
    evidence = base_evidence()
    assert evaluate_qualification_applicability(
        evidence, base_candidate(workflow_id="wf-v2")
    ) == "stale"


def test_scenario_case_f_provider_requires_fresh_check() -> None:
    evidence = base_evidence()
    candidate = base_candidate(provider_mandates_fresh_check=True)
    assert evaluate_qualification_applicability(evidence, candidate) == "stale"


def test_material_external_binding_changes_each_invalidate_evidence() -> None:
    evidence = base_evidence()
    mutations = {
        "generated_state_id": "generated-v2",
        "dependency_id": "deps-v2",
        "lockfile_id": "lock-v2",
        "toolchain_id": "toolchain-v2",
        "validation_environment_id": "env-v2",
    }

    for field, changed_value in mutations.items():
        candidate = base_candidate(**{field: changed_value})
        assert evaluate_qualification_applicability(evidence, candidate) == "stale", field


def test_unknown_state_and_unknown_binding_fail_closed() -> None:
    evidence = base_evidence()
    assert evaluate_qualification_applicability(
        evidence, base_candidate(is_known=False)
    ) == "unknown"
    assert evaluate_qualification_applicability(
        base_evidence(binding_class="unknown"), base_candidate()
    ) == "unknown"
