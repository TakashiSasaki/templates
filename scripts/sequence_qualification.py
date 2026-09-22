#!/usr/bin/env python3
"""Qualification and dependency sequencing engine for Policy maintainer workflows.

Determines safe execution frontiers, defers premature downstream repins/qualifications,
manages selective evidence invalidation and reuse, and computes the next safe resumable action.

Principles:
1. Separate observe -> plan -> explicit authorization -> mutate -> verify.
2. The planning path is strictly read-only.
3. Repin mutations require explicit authorization and exact expected-old-state guards.
4. Selective evidence invalidation: only invalidate evidence whose exact bound inputs have changed.
5. Fail closed on incomplete, contradictory, or unexpected states.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA_PATTERN = re.compile(r"\b[0-9a-f]{40}\b")
MAX_SUMMARY_BYTES = 8192

# Frontiers
FRONTIER_CONSTRUCTION = "construction"
FRONTIER_QUALIFICATION = "qualification"
FRONTIER_ADOPTION = "adoption"
FRONTIER_BLOCKED = "blocked"

# Actions
ACTION_CONSTRUCTION_ALLOWED = "construction_allowed"
ACTION_FOCUSED_VALIDATION_ALLOWED = "focused_validation_allowed"
ACTION_UPSTREAM_ACCEPTANCE_PENDING = "upstream_acceptance_pending"
ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED = "downstream_final_pin_deferred"
ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED = "downstream_final_qualification_deferred"
ACTION_DOWNSTREAM_PIN_READY = "downstream_pin_ready"
ACTION_FINAL_QUALIFICATION_READY = "final_qualification_ready"
ACTION_REVIEW_ACQUISITION_READY = "review_acquisition_ready"
ACTION_NO_OP = "no_op"
ACTION_BLOCKED_INCOMPLETE = "blocked_incomplete"

VALID_STABILITIES = {"mutating", "frozen", "accepted"}
VALID_QUALIFICATION_STATES = {"untested", "in_progress", "passed", "failed"}
VALID_ACCEPTANCE_STATES = {"unreviewed", "in_progress", "accepted", "rejected"}


class SequencingError(Exception):
    """Raised when sequencing encounters invalid, contradictory, or unauthorized state."""


def validate_facts_schema(facts: dict[str, Any]) -> list[str]:
    """Validate machine-readable facts and return any validation errors."""
    errors: list[str] = []
    if not isinstance(facts, dict):
        return ["facts must be a dictionary"]

    if facts.get("schema_version") != 1:
        errors.append(f"unsupported schema_version: {facts.get('schema_version')}")

    upstream = facts.get("upstream")
    if not isinstance(upstream, dict):
        errors.append("missing or invalid 'upstream' section")
    else:
        cand_head = upstream.get("candidate_head")
        if not cand_head or not FULL_SHA.fullmatch(str(cand_head)):
            errors.append(f"upstream candidate_head must be a 40-char lowercase SHA: {cand_head}")

        stability = upstream.get("stability")
        if stability not in VALID_STABILITIES:
            errors.append(
                f"upstream stability must be one of {sorted(VALID_STABILITIES)}: {stability}"
            )

        qual_state = upstream.get("qualification_state", "untested")
        if qual_state not in VALID_QUALIFICATION_STATES:
            errors.append(f"upstream qualification_state invalid: {qual_state}")

        acc_state = upstream.get("acceptance_state", "unreviewed")
        if acc_state not in VALID_ACCEPTANCE_STATES:
            errors.append(f"upstream acceptance_state invalid: {acc_state}")

        # Contradiction check: accepted stability with planned mutations
        planned = upstream.get("planned_mutations", [])
        if not isinstance(planned, list):
            errors.append("upstream planned_mutations must be a list")
        elif stability == "accepted" and len(planned) > 0:
            errors.append("contradiction: upstream marked 'accepted' but has planned_mutations")

    downstream = facts.get("downstream")
    if downstream is not None:
        if not isinstance(downstream, dict):
            errors.append("downstream must be a dictionary if provided")
        else:
            for pin_field in ("current_pin", "desired_pin"):
                pin_val = downstream.get(pin_field)
                if pin_val and not FULL_SHA.fullmatch(str(pin_val)):
                    errors.append(
                        f"downstream {pin_field} must be a 40-char lowercase SHA: {pin_val}"
                    )

    return errors


def plan_repin_guard(
    expected_old_pin: str,
    desired_pin: str,
    actual_pin: str,
) -> dict[str, str]:
    """Pure read-only decision on whether repin is no-op, eligible, or blocked."""
    if not FULL_SHA.fullmatch(expected_old_pin):
        raise SequencingError(f"invalid expected_old_pin SHA: {expected_old_pin}")
    if not FULL_SHA.fullmatch(desired_pin):
        raise SequencingError(f"invalid desired_pin SHA: {desired_pin}")
    if not FULL_SHA.fullmatch(actual_pin):
        raise SequencingError(f"invalid actual_pin SHA: {actual_pin}")

    if actual_pin == desired_pin:
        return {
            "status": "no_op",
            "message": "downstream already points to desired pin; no mutation needed",
            "current_pin": actual_pin,
            "desired_pin": desired_pin,
        }
    elif actual_pin == expected_old_pin:
        return {
            "status": "eligible",
            "message": "actual pin matches expected old pin; authorized mutation may proceed",
            "current_pin": actual_pin,
            "desired_pin": desired_pin,
        }
    else:
        return {
            "status": "blocked",
            "message": (
                f"unexpected downstream pin: expected {expected_old_pin} "
                f"but observed {actual_pin}; refusing silent overwrite of unexpected state"
            ),
            "current_pin": actual_pin,
            "desired_pin": desired_pin,
        }


def execute_guarded_repin(
    target_file: Path,
    expected_old_pin: str,
    new_pin: str,
    authorized: bool = False,
) -> dict[str, Any]:
    """Mutate a downstream pin file only with explicit authorization and expected-old-pin match."""
    if not authorized:
        raise SequencingError("repin mutation refused: explicit authorization is required")

    if not target_file.is_file():
        raise SequencingError(f"target pin file not found: {target_file}")

    content = target_file.read_text(encoding="utf-8")
    actual_match = SHA_PATTERN.search(content)
    if not actual_match:
        raise SequencingError(f"no 40-char SHA found in {target_file}")

    actual_pin = actual_match.group(0)
    decision = plan_repin_guard(expected_old_pin, new_pin, actual_pin)

    if decision["status"] == "no_op":
        return {"mutated": False, "status": "no_op", "pin": actual_pin}

    if decision["status"] == "blocked":
        raise SequencingError(f"repin mutation blocked: {decision['message']}")

    # Apply guarded mutation
    updated_content = content[: actual_match.start()] + new_pin + content[actual_match.end() :]
    target_file.write_text(updated_content, encoding="utf-8")
    return {"mutated": True, "status": "repointed", "old_pin": actual_pin, "new_pin": new_pin}


def evaluate_evidence(
    evidence_list: list[dict[str, Any]],
    current_upstream_head: str,
    current_downstream_pin: str | None,
) -> tuple[list[str], list[str]]:
    """Partition evidence into reusable and invalidated (stale) based on exact bindings."""
    reusable: list[str] = []
    invalidated: list[str] = []

    for ev in evidence_list:
        ev_id = ev.get("evidence_id", "unidentified_evidence")
        bound = ev.get("bound_inputs", {})
        bound_upstream = bound.get("upstream_head")
        bound_downstream = bound.get("downstream_pin")

        # Must have passed originally
        if ev.get("status") != "passed":
            invalidated.append(ev_id)
            continue

        # Check upstream binding
        if bound_upstream != current_upstream_head:
            invalidated.append(ev_id)
            continue

        # Check downstream pin binding if specified
        if (
            bound_downstream
            and current_downstream_pin
            and bound_downstream != current_downstream_pin
        ):
            invalidated.append(ev_id)
            continue

        reusable.append(ev_id)

    return reusable, invalidated


def sequence_qualification(facts: dict[str, Any]) -> dict[str, Any]:
    """Evaluate machine-readable qualification facts and return a bounded sequencing result."""
    validation_errors = validate_facts_schema(facts)
    if validation_errors:
        return {
            "schema_version": 1,
            "current_frontier": FRONTIER_BLOCKED,
            "allowed_actions": [],
            "deferred_actions": [],
            "blocking_reasons": validation_errors,
            "invalidated_evidence": [],
            "reusable_evidence": [],
            "next_safe_action": "fail_closed_resolve_contradiction",
            "resume_boundary": "validation_failure",
        }

    upstream = facts["upstream"]
    cand_head = upstream["candidate_head"]
    stability = upstream["stability"]
    planned_mutations = upstream.get("planned_mutations", [])
    acceptance_state = upstream.get("acceptance_state", "unreviewed")
    qual_state = upstream.get("qualification_state", "untested")

    downstream = facts.get("downstream", {})
    current_pin = downstream.get("current_pin")
    desired_pin = downstream.get("desired_pin")
    actual_pin = downstream.get("actual_pin", current_pin)

    readiness = facts.get("readiness", {})
    material_findings_open = readiness.get("material_findings_open", 0)
    sibling_audit_complete = readiness.get("sibling_audit_complete", True)

    # Checkpoint / completed actions
    checkpoint = facts.get("checkpoint", {})
    completed_actions = set(checkpoint.get("completed_actions", []))

    # Evaluate existing evidence
    evidence_list = facts.get("validation_evidence", [])
    reusable_evidence, invalidated_evidence = evaluate_evidence(
        evidence_list,
        current_upstream_head=cand_head,
        current_downstream_pin=current_pin,
    )

    allowed_actions: list[str] = []
    deferred_actions: list[str] = []
    blocking_reasons: list[str] = []
    repin_decision: dict[str, str] | None = None

    # Check repin state if downstream is specified
    if current_pin and desired_pin:
        repin_decision = plan_repin_guard(
            expected_old_pin=current_pin,
            desired_pin=desired_pin,
            actual_pin=actual_pin,
        )
        if repin_decision["status"] == "blocked":
            blocking_reasons.append(repin_decision["message"])

    # 1. Blocked frontier due to material findings or repin conflict
    if material_findings_open > 0 or not sibling_audit_complete or blocking_reasons:
        current_frontier = FRONTIER_BLOCKED
        if material_findings_open > 0:
            blocking_reasons.append(f"material findings open: count={material_findings_open}")
        if not sibling_audit_complete:
            blocking_reasons.append("sibling audit incomplete for active finding family")

        # Allow focused diagnostic work, defer everything else
        if ACTION_FOCUSED_VALIDATION_ALLOWED not in completed_actions:
            allowed_actions.append(ACTION_FOCUSED_VALIDATION_ALLOWED)
        deferred_actions.extend([
            ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED,
            ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED,
            ACTION_REVIEW_ACQUISITION_READY,
        ])
        next_safe_action = "resolve_open_findings"
        resume_boundary = "findings_closure"

    # 2. Construction frontier (upstream still changing)
    elif stability == "mutating" or len(planned_mutations) > 0:
        current_frontier = FRONTIER_CONSTRUCTION
        allowed_actions.extend([
            ACTION_CONSTRUCTION_ALLOWED,
            ACTION_FOCUSED_VALIDATION_ALLOWED,
        ])
        deferred_actions.extend([
            ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED,
            ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED,
            ACTION_REVIEW_ACQUISITION_READY,
        ])
        next_safe_action = (
            "continue_focused_construction"
            if ACTION_FOCUSED_VALIDATION_ALLOWED not in completed_actions
            else "await_upstream_freeze"
        )
        resume_boundary = "upstream_freeze"

    # 3. Qualification frontier (upstream candidate frozen, not yet accepted)
    elif stability == "frozen" and acceptance_state != "accepted":
        current_frontier = FRONTIER_QUALIFICATION
        allowed_actions.extend([
            ACTION_CONSTRUCTION_ALLOWED,
            ACTION_FOCUSED_VALIDATION_ALLOWED,
            ACTION_UPSTREAM_ACCEPTANCE_PENDING,
        ])
        deferred_actions.extend([
            ACTION_DOWNSTREAM_FINAL_PIN_DEFERRED,
            ACTION_DOWNSTREAM_FINAL_QUALIFICATION_DEFERRED,
        ])
        if qual_state == "passed":
            next_safe_action = "await_upstream_acceptance"
        else:
            next_safe_action = "run_upstream_qualification"
        resume_boundary = "upstream_acceptance"

    # 4. Adoption frontier (upstream accepted)
    elif stability == "accepted" and acceptance_state == "accepted":
        current_frontier = FRONTIER_ADOPTION

        if repin_decision and repin_decision["status"] == "no_op":
            allowed_actions.extend([
                ACTION_NO_OP,
                ACTION_FINAL_QUALIFICATION_READY,
                ACTION_REVIEW_ACQUISITION_READY,
            ])
            next_safe_action = "run_final_qualification"
            resume_boundary = "final_review"
        else:
            allowed_actions.extend([
                ACTION_DOWNSTREAM_PIN_READY,
                ACTION_FINAL_QUALIFICATION_READY,
            ])
            next_safe_action = "materialize_downstream_pin"
            resume_boundary = "downstream_repin"
    else:
        # Catch-all safe fallback
        current_frontier = FRONTIER_BLOCKED
        blocking_reasons.append(
            f"unhandled state combination: stability={stability}, acceptance={acceptance_state}"
        )
        next_safe_action = "fail_closed_resolve_contradiction"
        resume_boundary = "state_reconciliation"

    # Filter out actions already recorded as completed in checkpoint
    filtered_allowed = [a for a in allowed_actions if a not in completed_actions]

    result: dict[str, Any] = {
        "schema_version": 1,
        "objective": facts.get("objective", "unspecified_objective"),
        "current_frontier": current_frontier,
        "allowed_actions": filtered_allowed,
        "deferred_actions": deferred_actions,
        "blocking_reasons": blocking_reasons,
        "invalidated_evidence": invalidated_evidence,
        "reusable_evidence": reusable_evidence,
        "next_safe_action": next_safe_action,
        "resume_boundary": resume_boundary,
    }

    if repin_decision:
        result["repin_decision"] = repin_decision

    # Ensure bounded summary size <= MAX_SUMMARY_BYTES
    dumped = json.dumps(result, indent=2)
    if len(dumped.encode("utf-8")) > MAX_SUMMARY_BYTES:
        result["invalidated_evidence"] = result["invalidated_evidence"][:5]
        result["reusable_evidence"] = result["reusable_evidence"][:5]

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        help="path to JSON facts file (default: read from stdin)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="path to output JSON sequencing result (default: write to stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="format JSON output with indentation",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.input and args.input != "-":
            facts = json.loads(Path(args.input).read_text(encoding="utf-8"))
        else:
            facts = json.load(sys.stdin)
    except Exception as exc:
        print(f"ERROR: failed to read input facts: {exc}", file=sys.stderr)
        return 2

    result = sequence_qualification(facts)
    indent = 2 if args.pretty else None
    output_str = json.dumps(result, indent=indent) + "\n"

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
    else:
        sys.stdout.write(output_str)

    if result["current_frontier"] == FRONTIER_BLOCKED and result["blocking_reasons"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
