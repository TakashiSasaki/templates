from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.automation_boundaries import (  # noqa: E402
    CANONICAL_OPERATION_REGISTRY,
    AutomationBoundaryError,
    OperationCategory,
    enforce_acceptance_separation,
    enforce_operation_permission,
)
from scripts.orchestrate_preflights import orchestrate_preflights  # noqa: E402
from scripts.sequence_qualification import (  # noqa: E402
    FRONTIER_BLOCKED,
    FRONTIER_QUALIFICATION,
    SequencingError,
    execute_guarded_repin,
    sequence_qualification,
)

FAKE_SHA_1 = "1111111111111111111111111111111111111111"
FAKE_SHA_2 = "2222222222222222222222222222222222222222"


def test_observation_cannot_approve() -> None:
    """1. Observation cannot approve: snapshots cannot produce acceptance or merge."""
    contract = CANONICAL_OPERATION_REGISTRY["observe_pr_state"]
    assert contract.category == OperationCategory.MECHANICAL_READ_OR_LOCAL
    assert contract.may_establish_acceptance is False
    assert contract.may_authorize_merge is False

    # Enforce permission check passes for read-only observation but cannot authorize
    enforce_operation_permission("observe_pr_state")


def test_qualification_sequencing_cannot_manufacture_acceptance() -> None:
    """2. Qualification sequencing cannot manufacture acceptance when acceptance is unreviewed."""
    facts = {
        "schema_version": 1,
        "objective": "test_boundary",
        "upstream": {
            "candidate_head": FAKE_SHA_1,
            "stability": "frozen",
            "qualification_state": "passed",  # All tests passed!
            "acceptance_state": "unreviewed",  # But review has NOT occurred
        },
    }

    result = sequence_qualification(facts)
    # Must remain in qualification frontier, NOT adoption
    assert result["current_frontier"] == FRONTIER_QUALIFICATION
    assert result["next_safe_action"] == "await_upstream_acceptance"
    assert "materialize_downstream_pin" not in result["allowed_actions"]
    assert result["is_validation_evidence_only"] is True
    assert result["may_establish_acceptance"] is False
    assert result["may_authorize_merge"] is False


def test_preflight_pass_is_not_review_acceptance(tmp_path: Path) -> None:
    """3. Preflight PASS is not review acceptance: preflight is validation evidence only."""
    res = orchestrate_preflights(
        authorities=[],
        repo_root=tmp_path,
    )
    assert res["is_validation_evidence_only"] is True
    assert res["may_establish_acceptance"] is False

    contract = CANONICAL_OPERATION_REGISTRY["orchestrate_preflights"]
    assert contract.may_establish_acceptance is False
    assert contract.may_authorize_merge is False


def test_review_planner_cannot_merge() -> None:
    """4. Review planner cannot merge: planner contract prohibits merge authorization."""
    contract = CANONICAL_OPERATION_REGISTRY["plan_review_scope"]
    assert contract.category == OperationCategory.MECHANICAL_READ_OR_LOCAL
    assert contract.may_authorize_merge is False
    assert contract.may_establish_acceptance is False


def test_unauthorized_guarded_mutation_fails(tmp_path: Path) -> None:
    """5. Unauthorized guarded mutation fails: missing authorized=True must fail closed."""
    target_pin_file = tmp_path / "pin.txt"
    target_pin_file.write_text(f"pin: {FAKE_SHA_1}\n", encoding="utf-8")

    # execute_guarded_repin without authorized=True must raise
    with pytest.raises(
        SequencingError,
        match="repin mutation refused: explicit authorization is required",
    ):
        execute_guarded_repin(
            target_file=target_pin_file,
            expected_old_pin=FAKE_SHA_1,
            new_pin=FAKE_SHA_2,
            authorized=False,
        )

    # enforce_operation_permission for guarded mutation without authorization must raise
    with pytest.raises(AutomationBoundaryError, match="explicit authorization is required"):
        enforce_operation_permission("execute_guarded_repin", authorized=False)

    with pytest.raises(AutomationBoundaryError, match="explicit authorization is required"):
        enforce_operation_permission("publish_review_artifacts", authorized=False)


def test_unknown_semantic_result_fails_closed() -> None:
    """6. Unknown semantic result fails closed: contradictory or missing judgment halts routing."""
    # Open material findings block progression
    facts_with_open_findings = {
        "schema_version": 1,
        "upstream": {
            "candidate_head": FAKE_SHA_1,
            "stability": "accepted",
            "acceptance_state": "accepted",
        },
        "readiness": {
            "material_findings_open": 2,
            "sibling_audit_complete": False,
        },
    }
    res = sequence_qualification(facts_with_open_findings)
    assert res["current_frontier"] == FRONTIER_BLOCKED
    assert res["next_safe_action"] == "resolve_open_findings"
    assert "material findings open: count=2" in res["blocking_reasons"]

    # Contradictory state: accepted stability with planned mutations fails closed
    facts_contradictory = {
        "schema_version": 1,
        "upstream": {
            "candidate_head": FAKE_SHA_1,
            "stability": "accepted",
            "planned_mutations": ["repair_bug_commit"],
        },
    }
    res_contradiction = sequence_qualification(facts_contradictory)
    assert res_contradiction["current_frontier"] == FRONTIER_BLOCKED
    assert res_contradiction["next_safe_action"] == "fail_closed_resolve_contradiction"


def test_human_controlled_transition_remains_external() -> None:
    """7. Human-controlled transition remains external: automated helpers cannot make decisions."""
    for op in ("authorize_merge", "authorize_self_host_adoption", "authorize_publication_cutover"):
        contract = CANONICAL_OPERATION_REGISTRY[op]
        assert contract.category == OperationCategory.AUTHORITY_CONTROLLED_DECISION
        assert contract.requires_authorization is True

        # Automated helpers attempting to execute authority decisions fail closed
        with pytest.raises(AutomationBoundaryError, match="authority-controlled decision"):
            enforce_operation_permission(op, caller_is_automated_helper=True, authorized=False)

    # Acceptance separation: validation PASS alone cannot claim review acceptance
    with pytest.raises(AutomationBoundaryError, match="acceptance separation violation"):
        enforce_acceptance_separation("passed", "accepted", has_external_acceptance_evidence=False)
