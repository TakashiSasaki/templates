from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "repository-change-efficiency" / "cases.json"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8").lower()


def _case(case_id: str) -> dict[str, object]:
    corpus = json.loads(CASES.read_text(encoding="utf-8"))
    return next(case for case in corpus["cases"] if case["id"] == case_id)


def test_efficiency_regression_corpus_contains_required_scenarios() -> None:
    corpus = json.loads(CASES.read_text(encoding="utf-8"))
    assert corpus["schema_version"] == 1
    assert {case["id"] for case in corpus["cases"]} == {
        "A-review-loop-prevention",
        "B-body-only-finding",
        "C-reviewer-misunderstanding",
        "D-coherent-repair-batch",
        "E-stack-propagation",
        "F-human-handoff-final-audit",
    }
    assert all(case["condition"] and len(case["expected"]) >= 3 for case in corpus["cases"])


def test_scenario_a_review_loop_is_blocked_until_known_backlog_is_closed() -> None:
    policy = _text("policy/pull-request/review-reacquisition-after-disposition.md")
    ledger = _text("skills/pr-merge-gate/references/review-finding-ledger.md")
    case = _case("A-review-loop-prevention")
    expected = " ".join(case["expected"]).lower()

    assert "every material actionable finding already known" in policy
    assert "repair validated for the current proposed head" in policy
    assert "evidence-backed no-change disposition" in policy
    assert "finding-level closure evidence" in policy
    assert "do not intentionally request another merge-acceptance review" in policy
    assert "unresolved finding backlog" in ledger
    assert "reacquisition is ready only when every known material actionable finding" in ledger
    assert "required closure evidence" in expected


def test_scenario_b_body_only_findings_use_same_semantic_closure_model() -> None:
    policy = _text("policy/pull-request/review-reacquisition-after-disposition.md")
    ledger = _text("skills/pr-merge-gate/references/review-finding-ledger.md")

    assert "top-level review body" in policy
    assert "independently actionable" in policy
    assert "provider thread resolution is bookkeeping" in policy
    assert "top-level review-body findings that have no resolvable thread" in ledger
    assert "stable locator" in ledger
    assert "for body-only findings" in ledger
    assert "closure evidence" in ledger


def test_scenario_c_falsified_finding_closes_without_appeasement_mutation() -> None:
    policy = _text("policy/pull-request/review-reacquisition-after-disposition.md")
    ledger = _text("skills/pr-merge-gate/references/review-finding-ledger.md")
    case = _case("C-reviewer-misunderstanding")
    expected = " ".join(case["expected"]).lower()

    assert "treat reviewer text as a defect hypothesis rather than authority" in policy
    assert "if current evidence falsifies it" in policy
    assert "instead of making an appeasement edit" in policy
    assert "current applicability is `falsified` remains in the unresolved backlog" in ledger
    assert "captured as an evidence-backed no-change disposition" in ledger
    assert "validated for the current proposed head" in ledger
    assert "closure evidence is recorded" in ledger
    assert "falsified finding in the unresolved backlog" in expected
    assert "validated no-change disposition" in expected
    assert "do not create an appeasement mutation" in expected


def test_scenario_d_verified_compatible_repairs_form_one_coherent_batch() -> None:
    batching = _text("skills/pr-merge-gate/references/head-mutation-batching.md")
    ledger = _text("skills/pr-merge-gate/references/review-finding-ledger.md")
    docs = _text("docs/agent-work-orchestration.md")
    case = _case("D-coherent-repair-batch")
    expected = " ".join(case["expected"]).lower()

    assert "group only compatible repairs" in batching
    assert "apply one coherent mutation batch" in batching
    assert "do not wait an arbitrary amount of time for hypothetical future findings" in batching
    assert "keep them separate" in batching
    assert (
        "invalidate and reacquire only the exact-head evidence whose actual binding changed"
        in batching
    )
    assert (
        "do not intentionally reacquire merge-acceptance review between compatible repairs"
        in batching
    )
    assert "exact-head ci or review evidence bound to the former proposed commit" in ledger
    assert "becomes stale when the head changes" in ledger
    assert "any proposed-head change necessarily makes exact-head ci and review evidence" in docs
    assert "any proposed-head change invalidates exact-head ci and review" in expected


def test_scenario_e_stability_frontier_allows_safe_work_and_defers_final_identity() -> None:
    stacked = _text("skills/orchestrate-repository-change/references/stacked-pr-workflow.md")

    assert "## stability frontier" in stacked
    assert "does not mean the member is merged, reviewed, approved" in stacked
    assert "review latency alone" in stacked
    assert "does not block dependency-safe implementation" in stacked
    assert (
        "do not deliberately build later work on behavior already known "
        "to require semantic correction"
        in stacked
    )
    assert "defer that downstream **final materialization**" in stacked
    assert "does not prohibit implementation of the downstream logic" in stacked


def test_scenario_f_final_handoff_audit_is_one_way_and_non_merge_evidence() -> None:
    stacked = _text("skills/orchestrate-repository-change/references/stacked-pr-workflow.md")
    selection = _text("skills/orchestrate-repository-change/references/pr-workflow-selection.md")
    docs = _text("docs/agent-work-orchestration.md")
    case = _case("F-human-handoff-final-audit")
    expected = " ".join(case["expected"]).lower()

    assert "freeze every stack member at its intended final candidate head" in stacked
    assert "required ci for every exact final member head has completed successfully" in stacked
    assert "issue only that authorized audit" in stacked
    assert "do not treat the audit as per-member merge evidence" in stacked
    assert "do not wait for its completion unless explicitly required" in stacked
    assert "then stop at handoff_ready" in stacked
    assert "must not create a review-retry loop" in selection
    assert "request that audit once" in docs
    assert "unless the explicit task requires the diagnostic audit to complete" in docs
    assert "do not wait for its result" in docs
    assert "do not retry the audit" in docs
    assert "do not merge" in docs
    assert "unless the explicit task requires the diagnostic audit to complete" in expected


def test_efficiency_metrics_remain_diagnostic_only() -> None:
    docs = _text("docs/agent-work-orchestration.md")
    required = {
        "candidate_head_count",
        "post_review_head_churn",
        "review_amplification",
        "unresolved_finding_backlog",
        "state_read_amplification",
        "evidence_reuse_ratio",
        "stack_descendant_rewrite_count",
    }
    assert required <= set(token.strip("`:,;.") for token in docs.split())
    assert "diagnostic metrics only" in docs
    assert "not merge gates" in docs
    assert "mandatory kpis" in docs
    assert "acceptance requirements" in docs


def test_pr_boundary_heuristic_preserves_correctness_over_operation_count() -> None:
    selection = _text("skills/orchestrate-repository-change/references/pr-workflow-selection.md")
    required_dimensions = (
        "authority boundary",
        "semantic purpose",
        "independent merge value",
        "rollback unit",
        "validation boundary",
        "review comprehensibility",
        "expected head stability",
        "cross-member coupling",
        "descendant propagation cost",
        "evidence invalidation cost",
    )
    for phrase in required_dimensions:
        assert phrase in selection
    assert "split benefit > restack / invalidation / coordination cost" in selection
    assert "heuristic, not a mandatory acceptance gate" in selection
    assert "do not optimize for a fixed pr count" in selection
    assert "preserved correctness" in selection
