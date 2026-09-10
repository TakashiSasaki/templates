from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orchestrate-repository-change"
REFERENCES = SKILL / "references"
STACKED = REFERENCES / "stacked-pr-workflow.md"
STAGED = REFERENCES / "staged-ci-execution.md"
WORK_LEDGER = REFERENCES / "work-ledger.md"
ORCHESTRATION_DOCS = ROOT / "docs" / "agent-work-orchestration.md"


def test_stacked_landing_procedure_is_normative() -> None:
    stacked_text = STACKED.read_text(encoding="utf-8").lower()
    staged_text = STAGED.read_text(encoding="utf-8").lower()

    assert "merge progression does not itself invalidate qualification evidence" in stacked_text
    assert (
        "a change to the qualified candidate state or to an evidence binding does"
        in stacked_text
    )

    for step in (
        "land current stack member",
        "refresh next member's live state",
        "verify member preconditions",
        "compare existing qualification evidence bindings",
        "evaluate applicability per evidence item",
        "reuse applicable evidence",
        "reacquire only stale / unknown evidence",
        "progress to next member",
    ):
        assert step in stacked_text

    assert "evaluate qualification applicability across stacked landing" in staged_text
    assert "avoid blind full-suite reruns" in staged_text
    assert "exact-head review evidence for the prior head is stale" in staged_text
    assert "this exception applies to ci/qualification evidence only" in staged_text
    assert "never reuse prior exact-head review merely because the tree is unchanged" in staged_text


def test_stacked_landing_anti_pattern_is_explicitly_rejected() -> None:
    stacked_text = STACKED.read_text(encoding="utf-8").lower()

    assert "do **not** adopt the blind full-suite rerun pattern" in stacked_text or (
        "do not adopt the blind full-suite rerun pattern" in stacked_text
    )
    assert "merge a\n  -> rerun every ci on b" in stacked_text

    assert "merge a\n  -> refresh b\n  -> evaluate existing evidence applicability" in stacked_text
    assert "rerun only invalidated qualification" in stacked_text


def test_work_ledger_projection_of_qualification_evidence() -> None:
    ledger_text = WORK_LEDGER.read_text(encoding="utf-8").lower()
    staged_text = STAGED.read_text(encoding="utf-8").lower()

    for target in (ledger_text, staged_text):
        assert "qualification candidate" in target
        assert "qualified tree identity" in target
        assert "evidence binding" in target
        assert "applicability state" in target
        assert "invalidation reason" in target
        assert "reuse decision" in target
        assert "validation requiring reacquisition" in target

    assert "next safe landing action" in ledger_text
    assert "next safe landing action" in staged_text


def test_work_ledger_must_not_become_acceptance_authority() -> None:
    ledger_text = WORK_LEDGER.read_text(encoding="utf-8").lower()
    staged_text = STAGED.read_text(encoding="utf-8").lower()

    assert (
        "operational projection / resumable index, not a new source of semantic acceptance"
        in ledger_text
    )
    assert "canonical provider facts; ledger entries are observations" in ledger_text
    assert "do not create a second acceptance authority in the work ledger" in staged_text
    assert "ledger itself must never declare a member authorized to land" in staged_text
    assert "may invoke the merge gate" in staged_text


def test_orchestration_skills_render_cleanly() -> None:
    rendered = render_skill("orchestrate-repository-change")
    assert "references/stacked-pr-workflow.md" in rendered
    assert "references/staged-ci-execution.md" in rendered
    assert "references/work-ledger.md" in rendered

    installed_stacked = rendered["references/stacked-pr-workflow.md"]
    assert "Stacked pull-request landing and qualification evidence reuse" in installed_stacked


Applicability = Literal["applicable", "stale", "unknown"]


@dataclass
class CheckpointCheck:
    check_id: str
    bound_tree_sha: str
    bound_head_sha: str
    applicability: Applicability
    invalidation_reason: str | None = None
    reuse_decision: bool = False


@dataclass
class WorkLedgerState:
    stack_members: list[str]
    current_landing_member: str
    qualification_candidate: str
    qualification_head: str
    qualified_tree_identity: str
    checks: list[CheckpointCheck]
    next_safe_landing_action: str


def reconstruct_landing_action(ledger: WorkLedgerState) -> str:
    """Reconstruct the next operation without treating the ledger as merge authority."""
    reacquire_list = [
        c.check_id
        for c in ledger.checks
        if c.applicability in ("stale", "unknown") or not c.reuse_decision
    ]
    if reacquire_list:
        return f"reacquire_qualification:{','.join(reacquire_list)}"
    return f"invoke_merge_gate:{ledger.current_landing_member}"


def test_work_ledger_landing_action_reconstruction() -> None:
    ledger = WorkLedgerState(
        stack_members=["pr-1-A", "pr-2-B", "pr-3-C"],
        current_landing_member="pr-2-B",
        qualification_candidate="candidate-B",
        qualification_head="sha-B-head",
        qualified_tree_identity="tree-B-clean",
        checks=[
            CheckpointCheck(
                check_id="core-validation",
                bound_tree_sha="tree-B-clean",
                bound_head_sha="sha-B-prev",
                applicability="applicable",
                reuse_decision=True,
            ),
            CheckpointCheck(
                check_id="cross-authority-compat",
                bound_tree_sha="tree-B-clean",
                bound_head_sha="sha-B-prev",
                applicability="stale",
                invalidation_reason="cross-authority-revision-updated",
                reuse_decision=False,
            ),
        ],
        next_safe_landing_action="pending_evaluation",
    )

    action = reconstruct_landing_action(ledger)
    assert action == "reacquire_qualification:cross-authority-compat"

    ledger.checks[1] = CheckpointCheck(
        check_id="cross-authority-compat",
        bound_tree_sha="tree-B-clean",
        bound_head_sha="sha-B-head",
        applicability="applicable",
        reuse_decision=True,
    )
    assert reconstruct_landing_action(ledger) == "invoke_merge_gate:pr-2-B"


def test_work_ledger_never_authorizes_landing_from_cached_observations() -> None:
    ledger = WorkLedgerState(
        stack_members=["pr-1-A"],
        current_landing_member="pr-1-A",
        qualification_candidate="candidate-A",
        qualification_head="sha-A-head",
        qualified_tree_identity="tree-A-clean",
        checks=[],
        next_safe_landing_action="pending_evaluation",
    )

    action = reconstruct_landing_action(ledger)
    assert action == "invoke_merge_gate:pr-1-A"
    assert "authorized_to_land" not in action
