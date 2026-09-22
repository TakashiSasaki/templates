from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sequence_qualification import (  # noqa: E402
    ACTION_CONSTRUCTION_ALLOWED,
    ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED,
    ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED,
    ACTION_DOWNSTREAM_PIN_READY,
    ACTION_FINAL_QUALIFICATION_READY,
    ACTION_FOCUSED_VALIDATION_ALLOWED,
    ACTION_NO_OP,
    ACTION_REVIEW_ACQUISITION_READY,
    ACTION_UPSTREAM_ACCEPTANCE_PENDING,
    FRONTIER_ADOPTION,
    FRONTIER_BLOCKED,
    FRONTIER_CONSTRUCTION,
    FRONTIER_QUALIFICATION,
    MAX_SUMMARY_BYTES,
    SequencingError,
    execute_guarded_repin,
    plan_repin_guard,
    sequence_qualification,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40


def test_upstream_still_changing_defers_downstream_qualification() -> None:
    facts = {
        "schema_version": 1,
        "objective": "feature-auth-refactor",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "mutating",
            "qualification_state": "in_progress",
            "acceptance_state": "unreviewed",
            "planned_mutations": ["repair_token_parser"],
        },
        "downstream": {
            "authority": "composition",
            "current_pin": SHA_B,
            "desired_pin": SHA_A,
        },
    }
    result = sequence_qualification(facts)

    assert result["current_frontier"] == FRONTIER_CONSTRUCTION
    assert ACTION_CONSTRUCTION_ALLOWED in result["allowed_actions"]
    assert ACTION_FOCUSED_VALIDATION_ALLOWED in result["allowed_actions"]
    assert ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED in result["deferred_actions"]
    assert ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED in result["deferred_actions"]
    assert ACTION_REVIEW_ACQUISITION_READY in result["deferred_actions"]
    assert result["next_safe_action"] == "continue_focused_construction"
    assert result["resume_boundary"] == "upstream_freeze"


def test_upstream_frozen_not_yet_accepted_awaits_acceptance() -> None:
    facts = {
        "schema_version": 1,
        "objective": "freeze-and-qualify",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "frozen",
            "qualification_state": "passed",
            "acceptance_state": "in_progress",
            "planned_mutations": [],
        },
        "downstream": {
            "authority": "integration",
            "current_pin": SHA_B,
            "desired_pin": SHA_A,
        },
    }
    result = sequence_qualification(facts)

    assert result["current_frontier"] == FRONTIER_QUALIFICATION
    assert ACTION_CONSTRUCTION_ALLOWED in result["allowed_actions"]
    assert ACTION_FOCUSED_VALIDATION_ALLOWED in result["allowed_actions"]
    assert ACTION_UPSTREAM_ACCEPTANCE_PENDING in result["allowed_actions"]
    assert ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED in result["deferred_actions"]
    assert ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED in result["deferred_actions"]
    assert result["next_safe_action"] == "await_upstream_acceptance"
    assert result["resume_boundary"] == "upstream_acceptance"


def test_upstream_accepted_allows_downstream_pin_materialization() -> None:
    facts = {
        "schema_version": 1,
        "objective": "adopt-upstream-toolchain",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "accepted",
            "qualification_state": "passed",
            "acceptance_state": "accepted",
            "planned_mutations": [],
        },
        "downstream": {
            "authority": "composition",
            "current_pin": SHA_B,
            "desired_pin": SHA_A,
        },
    }
    result = sequence_qualification(facts)

    assert result["current_frontier"] == FRONTIER_ADOPTION
    assert ACTION_DOWNSTREAM_PIN_READY in result["allowed_actions"]
    assert ACTION_FINAL_QUALIFICATION_READY in result["allowed_actions"]
    assert result["next_safe_action"] == "materialize_downstream_pin"
    assert result["resume_boundary"] == "downstream_repin"
    assert result["repin_decision"]["status"] == "eligible"


def test_downstream_already_pinned_is_no_op() -> None:
    facts = {
        "schema_version": 1,
        "objective": "verify-adopted-pin",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "accepted",
            "qualification_state": "passed",
            "acceptance_state": "accepted",
            "planned_mutations": [],
        },
        "downstream": {
            "authority": "site",
            "current_pin": SHA_A,
            "desired_pin": SHA_A,
            "actual_pin": SHA_A,
        },
    }
    result = sequence_qualification(facts)

    assert result["current_frontier"] == FRONTIER_ADOPTION
    assert ACTION_NO_OP in result["allowed_actions"]
    assert ACTION_FINAL_QUALIFICATION_READY in result["allowed_actions"]
    assert ACTION_REVIEW_ACQUISITION_READY in result["allowed_actions"]
    assert result["next_safe_action"] == "run_final_qualification"
    assert result["repin_decision"]["status"] == "no_op"


def test_selective_evidence_reuse_and_invalidation() -> None:
    facts = {
        "schema_version": 1,
        "objective": "evaluate-evidence-reuse",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "frozen",
            "qualification_state": "passed",
            "acceptance_state": "in_progress",
            "planned_mutations": [],
        },
        "downstream": {
            "authority": "composition",
            "current_pin": SHA_B,
            "desired_pin": SHA_A,
        },
        "validation_evidence": [
            {
                "evidence_id": "ev_matching",
                "bound_inputs": {
                    "upstream_head": SHA_A,
                    "downstream_pin": SHA_B,
                },
                "status": "passed",
            },
            {
                "evidence_id": "ev_stale_upstream",
                "bound_inputs": {
                    "upstream_head": SHA_C,
                    "downstream_pin": SHA_B,
                },
                "status": "passed",
            },
            {
                "evidence_id": "ev_stale_downstream",
                "bound_inputs": {
                    "upstream_head": SHA_A,
                    "downstream_pin": SHA_D,
                },
                "status": "passed",
            },
            {
                "evidence_id": "ev_failed",
                "bound_inputs": {
                    "upstream_head": SHA_A,
                    "downstream_pin": SHA_B,
                },
                "status": "failed",
            },
        ],
    }
    result = sequence_qualification(facts)

    assert "ev_matching" in result["reusable_evidence"]
    assert "ev_stale_upstream" in result["invalidated_evidence"]
    assert "ev_stale_downstream" in result["invalidated_evidence"]
    assert "ev_failed" in result["invalidated_evidence"]


def test_partial_execution_resumes_from_next_action() -> None:
    facts = {
        "schema_version": 1,
        "objective": "resume-after-restart",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "mutating",
            "planned_mutations": ["work_in_progress"],
        },
        "checkpoint": {
            "completed_actions": [ACTION_FOCUSED_VALIDATION_ALLOWED],
            "last_boundary": "focused_tests_completed",
        },
    }
    result = sequence_qualification(facts)

    # ACTION_FOCUSED_VALIDATION_ALLOWED is not replayed
    assert ACTION_FOCUSED_VALIDATION_ALLOWED not in result["allowed_actions"]
    assert ACTION_CONSTRUCTION_ALLOWED in result["allowed_actions"]
    assert result["next_safe_action"] == "await_upstream_freeze"


def test_contradictory_and_incomplete_state_fails_closed() -> None:
    # Contradiction: marked accepted but has planned mutations
    bad_facts = {
        "schema_version": 1,
        "objective": "contradictory-state",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "accepted",
            "planned_mutations": ["should_not_exist_on_accepted"],
        },
    }
    result = sequence_qualification(bad_facts)
    assert result["current_frontier"] == FRONTIER_BLOCKED
    assert len(result["allowed_actions"]) == 0
    assert any("contradiction" in b for b in result["blocking_reasons"])
    assert result["next_safe_action"] == "fail_closed_resolve_contradiction"

    # Incomplete facts: invalid candidate_head SHA
    bad_sha_facts = {
        "schema_version": 1,
        "objective": "bad-sha",
        "upstream": {
            "candidate_head": "invalid-sha",
            "stability": "frozen",
        },
    }
    result2 = sequence_qualification(bad_sha_facts)
    assert result2["current_frontier"] == FRONTIER_BLOCKED
    assert any("candidate_head must be a 40-char" in b for b in result2["blocking_reasons"])


def test_plan_repin_guard_decisions() -> None:
    # No-op case: actual equals desired
    res_noop = plan_repin_guard(expected_old_pin=SHA_A, desired_pin=SHA_B, actual_pin=SHA_B)
    assert res_noop["status"] == "no_op"

    # Eligible case: actual equals expected old
    res_eligible = plan_repin_guard(expected_old_pin=SHA_A, desired_pin=SHA_B, actual_pin=SHA_A)
    assert res_eligible["status"] == "eligible"

    # Blocked case: actual does not match expected old
    res_blocked = plan_repin_guard(expected_old_pin=SHA_A, desired_pin=SHA_B, actual_pin=SHA_C)
    assert res_blocked["status"] == "blocked"
    assert "unexpected downstream pin" in res_blocked["message"]


def test_execute_guarded_repin_enforces_authorization_and_expected_old_pin(
    tmp_path: Path,
) -> None:
    pin_file = tmp_path / "test_pin.yml"
    pin_file.write_text(f"toolchain_pin: {SHA_A}\n", encoding="utf-8")

    # Unauthorized attempt fails closed
    with pytest.raises(SequencingError, match="explicit authorization is required"):
        execute_guarded_repin(
            target_file=pin_file,
            expected_old_pin=SHA_A,
            new_pin=SHA_B,
            authorized=False,
        )
    assert SHA_A in pin_file.read_text(encoding="utf-8")

    # Unexpected actual pin fails closed
    with pytest.raises(SequencingError, match="unexpected downstream pin"):
        execute_guarded_repin(
            target_file=pin_file,
            expected_old_pin=SHA_C,  # expects C, but file has A
            new_pin=SHA_B,
            authorized=True,
        )
    assert SHA_A in pin_file.read_text(encoding="utf-8")

    # Authorized attempt with matching expected pin succeeds
    mut_result = execute_guarded_repin(
        target_file=pin_file,
        expected_old_pin=SHA_A,
        new_pin=SHA_B,
        authorized=True,
    )
    assert mut_result["mutated"] is True
    assert SHA_B in pin_file.read_text(encoding="utf-8")

    # Subsequent run is no-op
    noop_result = execute_guarded_repin(
        target_file=pin_file,
        expected_old_pin=SHA_A,
        new_pin=SHA_B,
        authorized=True,
    )
    assert noop_result["mutated"] is False
    assert noop_result["status"] == "no_op"


def test_bounded_summary_size_guarantee() -> None:
    facts = {
        "schema_version": 1,
        "objective": "test-size-bound",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "frozen",
            "acceptance_state": "in_progress",
        },
        "validation_evidence": [
            {
                "evidence_id": f"ev_{i}_" + ("x" * 200),
                "bound_inputs": {"upstream_head": SHA_B, "downstream_pin": SHA_C},
                "status": "passed",
            }
            for i in range(100)
        ],
    }
    result = sequence_qualification(facts)
    dumped = json.dumps(result, indent=2)
    assert len(dumped.encode("utf-8")) <= MAX_SUMMARY_BYTES


def test_cli_execution_with_input_and_output(tmp_path: Path) -> None:
    facts = {
        "schema_version": 1,
        "objective": "cli-test",
        "upstream": {
            "candidate_head": SHA_A,
            "stability": "accepted",
            "acceptance_state": "accepted",
        },
        "downstream": {
            "authority": "site",
            "current_pin": SHA_B,
            "desired_pin": SHA_A,
        },
    }
    in_file = tmp_path / "facts.json"
    in_file.write_text(json.dumps(facts), encoding="utf-8")
    out_file = tmp_path / "result.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sequence_qualification.py"),
            "--input",
            str(in_file),
            "--output",
            str(out_file),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI execution failed: {proc.stderr}"
    assert out_file.is_file()
    res = json.loads(out_file.read_text(encoding="utf-8"))
    assert res["current_frontier"] == FRONTIER_ADOPTION
    assert res["next_safe_action"] == "materialize_downstream_pin"
