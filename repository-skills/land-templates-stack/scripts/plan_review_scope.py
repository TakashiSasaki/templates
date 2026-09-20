#!/usr/bin/env python3
"""Select the next review action from an explicit, immutable review packet.

This helper is deliberately read-only.  It does not inspect a repository, call a
provider, submit a review, or establish merge authorization.  The maintenance
Skill supplies the live facts and the shared merge gate remains authoritative for
review evidence and acceptance.

Packets explicitly supply requests/reviews and discovery.requests_complete /
discovery.reviews_complete booleans after provider pagination and surface discovery.
Every EXPANSION_FLAGS field is required, including cross-member interaction.
Active request records bind candidate_binding/input_binding and their canonical
digests as well as the request key, status and actionable provider handle/locator.
Both active and completed records require request_binding and its digest, covering
repository, objective, purpose, candidate, explicit contract and material inputs.
Active records additionally require requested_scope; completed records instead
prove reviewed_scope dominance and actual coverage. Output exposes the canonical
binding to persist alongside the provider locator, without certifying its truth.
For cumulative merge acceptance, integration_base_tree_sha explicitly identifies
the tree of effective_base_sha; the adapter must obtain that identity from Git.
Incomplete discovery or inconsistent active metadata stops acquisition; it is not
an observed empty history and cannot justify a new external request.
For applicable request history (including scope-dominating broader requests),
unique provider cycle_id values and the explicitly
reconciled discovery.latest_request_cycle identify the latest applicable cycle;
array order and timestamps are not inferred. Only that cycle's completed result
can be reused. Failed/partial/unknown cycles require disposition, not fallback to
an older clean result. Every reusable result has an actionable source locator,
including independently discovered results without a local request record.
Early diagnostics cannot be requested under the merge_acceptance purpose.

``review_readiness`` is an optional schema-version-2 extension.  A missing or
unknown value is intentionally fail-closed for new external review acquisition;
it does not prevent reuse of applicable completed evidence or reconciliation of
an already-created request.  The renderer derives the value from the existing
Work-ledger closure audit, while this module validates the immutable packet
presented at the routing boundary.  When families are present, each family
must explicitly identify its disposition and sibling-audit completion.  The
readiness projection is not part of historical request applicability identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
REPOSITORY = "TakashiSasaki/templates"
FULL_SHA_LENGTH = 40

ACTION_REUSE = "reuse_existing_result"
ACTION_RECONCILE = "reconcile_existing_request"
ACTION_EARLY = "run_fixed_snapshot_diagnostic"
ACTION_DELTA = "request_independent_delta_review"
ACTION_STACK = "request_related_stack_review"
ACTION_MISSING = "acquire_missing_input_or_handoff"

RESULT_STATES = {
    "not_requested",
    "submission_unknown",
    "in_progress",
    "completed",
    "partial",
    "failed",
    "applicability_unknown",
    "stale",
}
PURPOSES = {
    "design_diagnostic",
    "finding_consultation",
    "fix_verification",
    "whole_stack_diagnostic",
    "merge_acceptance",
}
IMPACTS = {"bounded", "unbounded", "unknown"}
EXPANSION_FLAGS = (
    "contract_changed",
    "trust_boundary_changed",
    "topology_changed",
    "cross_member_interaction_changed",
)
REVIEW_READINESS_STATES = {"ready", "not_ready", "unknown"}
REVIEW_ACQUISITION_ACTIONS = {ACTION_EARLY, ACTION_DELTA, ACTION_STACK}


class RoutingInputError(ValueError):
    """Raised when a packet cannot support a safe routing decision."""


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RoutingInputError(f"{name} must be an object")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoutingInputError(f"{name} must be a non-empty string")
    return value


def _require_sha(value: Any, name: str) -> str:
    result = _require_string(value, name)
    if len(result) != FULL_SHA_LENGTH or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise RoutingInputError(f"{name} must be a lowercase full Git SHA")
    return result


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise RoutingInputError(f"{name} must be a list")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_json_data(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_data(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_data(item) for key, item in value.items())
    return False


def _validate_json_data(value: Any, name: str) -> Any:
    if not _is_json_data(value):
        raise RoutingInputError(f"{name} must be JSON data")
    return value


def _string_list(value: Any, name: str) -> list[str]:
    values = _require_list(value, name)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise RoutingInputError(f"{name} must contain non-empty strings")
    return sorted(set(values))


def normalize_review_readiness(value: Any) -> dict[str, Any]:
    """Validate the compact readiness projection used by review routing.

    Family validity and sibling reachability remain human/model judgment
    surfaces.  The planner only consumes their explicit, provenance-preserving
    result and enforces the acquisition boundary.
    """

    if value is None:
        return {
            "state": "unknown",
            "known_material_findings_complete": None,
            "finding_families": [],
            "planned_candidate_mutations": [],
            "remaining_material_gaps": ["review_readiness_not_supplied"],
            "reasons": ["review_readiness_not_supplied"],
            "exception": None,
            "review_acquisition_allowed": False,
        }
    readiness = _require_object(value, "review_readiness")
    declared_state = readiness.get("state")
    if declared_state is not None:
        declared_state = _require_string(declared_state, "review_readiness.state")
        if declared_state not in REVIEW_READINESS_STATES:
            raise RoutingInputError(
                "review_readiness.state must be ready, not_ready, or unknown"
            )

    known = readiness.get("known_material_findings_complete")
    if known is not None and type(known) is not bool:
        raise RoutingInputError(
            "review_readiness.known_material_findings_complete must be a boolean or null"
        )
    families = _require_list(
        readiness.get("finding_families", []), "review_readiness.finding_families"
    )
    normalized_families: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    reasons: list[str] = []
    remaining: list[str] = []
    for index, raw_family in enumerate(families):
        family = _require_object(raw_family, f"review_readiness.finding_families[{index}]")
        family_id = _require_string(
            family.get("id"), f"review_readiness.finding_families[{index}].id"
        )
        if family_id in seen_ids:
            raise RoutingInputError("review_readiness finding-family IDs must be unique")
        seen_ids.add(family_id)
        finding_refs = _string_list(
            family.get("finding_refs", []),
            f"review_readiness.finding_families[{index}].finding_refs",
        )
        sibling_complete = family.get("sibling_audit_complete")
        if type(sibling_complete) is not bool:
            raise RoutingInputError(
                "review_readiness.finding_families"
                f"[{index}].sibling_audit_complete must be a boolean"
            )
        gaps = _string_list(
            family.get("remaining_material_gaps", []),
            f"review_readiness.finding_families[{index}].remaining_material_gaps",
        )
        status = _require_string(
            family.get("status"),
            f"review_readiness.finding_families[{index}].status",
        )
        if status not in {"closed", "gap", "deliberately_untested"}:
            raise RoutingInputError(
                "review_readiness finding-family status must be closed, gap, "
                "or deliberately_untested"
            )
        if not sibling_complete:
            reason = f"sibling_audit_incomplete:{family_id}"
            reasons.append(reason)
            if not gaps:
                gaps = [reason]
        if gaps:
            reasons.extend(f"material_gap:{family_id}:{gap}" for gap in gaps)
            remaining.extend(f"{family_id}:{gap}" for gap in gaps)
        if status == "gap":
            reasons.append(f"family_open:{family_id}")
        if status == "deliberately_untested":
            reasons.append(f"deliberate_gap:{family_id}")
        normalized_families.append(
            {
                "id": family_id,
                "finding_refs": finding_refs,
                "sibling_audit_complete": sibling_complete,
                "remaining_material_gaps": gaps,
                **({"status": status} if status is not None else {}),
            }
        )

    planned = _string_list(
        readiness.get("planned_candidate_mutations", []),
        "review_readiness.planned_candidate_mutations",
    )
    if planned:
        reasons.append("planned_candidate_mutation")
        remaining.extend(f"planned_candidate_mutation:{item}" for item in planned)
    if known is None:
        reasons.append("review_readiness_unknown")
    elif known is not True:
        reasons.append("known_material_findings_incomplete")

    exception_value = readiness.get("exception")
    exception: dict[str, Any] | None
    if exception_value is None:
        exception = None
    else:
        exception = _require_object(exception_value, "review_readiness.exception")
        if type(exception.get("allow_new_review")) is not bool:
            raise RoutingInputError(
                "review_readiness.exception.allow_new_review must be a boolean"
            )
        _require_string(exception.get("reason"), "review_readiness.exception.reason")
        _require_string(
            exception.get("authority_ref"), "review_readiness.exception.authority_ref"
        )
        exception = {
            "allow_new_review": exception["allow_new_review"],
            "authority_ref": exception["authority_ref"],
            "reason": exception["reason"],
        }
        if exception["allow_new_review"]:
            reasons.append("explicit_review_exception")

    blocking_reasons = [
        reason for reason in reasons if reason != "explicit_review_exception"
    ]
    derived_state = (
        "unknown" if known is None else ("ready" if not blocking_reasons else "not_ready")
    )
    # The exception is an explicit, auditable override.  It never erases the
    # underlying not-ready reasons from the packet or checkpoint.
    allowed = derived_state == "ready" or bool(exception and exception["allow_new_review"])
    if declared_state is not None and declared_state != derived_state:
        raise RoutingInputError(
            "review_readiness.state does not match its structured evidence"
        )
    if "remaining_material_gaps" in readiness:
        declared_gaps = _string_list(
            readiness["remaining_material_gaps"],
            "review_readiness.remaining_material_gaps",
        )
        if declared_gaps != sorted(set(remaining)):
            raise RoutingInputError(
                "review_readiness.remaining_material_gaps does not match its families"
            )
    if "reasons" in readiness:
        declared_reasons = _string_list(readiness["reasons"], "review_readiness.reasons")
        if declared_reasons != sorted(set(reasons)):
            raise RoutingInputError("review_readiness.reasons does not match its evidence")
    if "review_acquisition_allowed" in readiness:
        if type(readiness["review_acquisition_allowed"]) is not bool:
            raise RoutingInputError(
                "review_readiness.review_acquisition_allowed must be a boolean"
            )
        if readiness["review_acquisition_allowed"] != allowed:
            raise RoutingInputError(
                "review_readiness.review_acquisition_allowed does not match its evidence"
            )
    return {
        "state": derived_state,
        "known_material_findings_complete": known,
        "finding_families": sorted(normalized_families, key=lambda item: item["id"]),
        "planned_candidate_mutations": planned,
        "remaining_material_gaps": sorted(set(remaining)),
        "reasons": sorted(set(reasons)),
        "exception": exception,
        "review_acquisition_allowed": allowed,
    }


def _input_binding(packet: dict[str, Any]) -> dict[str, Any]:
    binding = _require_object(packet.get("input_binding"), "input_binding")
    _validate_json_data(binding, "input_binding")
    return binding


def _require_bool(value: Any, name: str) -> bool:
    """Reject malformed scope flags instead of silently narrowing review scope."""
    if not isinstance(value, bool):
        raise RoutingInputError(f"{name} must be a boolean")
    return value


def _validate_members(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    members = _require_list(candidate.get("members"), "candidate.members")
    if not members:
        raise RoutingInputError("candidate.members must not be empty")
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(members):
        member = _require_object(raw, f"candidate.members[{index}]")
        _require_string(member.get("id"), f"candidate.members[{index}].id")
        if member["id"] in seen_ids:
            raise RoutingInputError("candidate member IDs must be unique")
        seen_ids.add(member["id"])
        _require_string(member.get("authority"), f"candidate.members[{index}].authority")
        _require_sha(member.get("base_sha"), f"candidate.members[{index}].base_sha")
        _require_sha(member.get("head_sha"), f"candidate.members[{index}].head_sha")
        result.append(member)
    return result


def _candidate_binding(candidate: dict[str, Any]) -> dict[str, Any]:
    members = _validate_members(candidate)
    binding = {
        "repository": _require_string(candidate.get("repository"), "candidate.repository"),
        "authority": _require_string(candidate.get("authority"), "candidate.authority"),
        "base_sha": _require_sha(candidate.get("base_sha"), "candidate.base_sha"),
        "effective_base_sha": _require_sha(
            candidate.get("effective_base_sha"), "candidate.effective_base_sha"
        ),
        "head_sha": _require_sha(candidate.get("head_sha"), "candidate.head_sha"),
        "members": [
            {
                "id": member["id"],
                "authority": member["authority"],
                "base_sha": member["base_sha"],
                "head_sha": member["head_sha"],
            }
            for member in members
        ],
    }
    if binding["repository"] != REPOSITORY:
        raise RoutingInputError("candidate.repository is not the templates repository")
    if "integration_base_tree_sha" in candidate:
        binding["integration_base_tree_sha"] = _require_sha(
            candidate["integration_base_tree_sha"], "candidate.integration_base_tree_sha"
        )
    authority_members = [
        member for member in members if member["authority"] == binding["authority"]
    ]
    if not authority_members or authority_members[-1]["head_sha"] != binding["head_sha"]:
        raise RoutingInputError("candidate head must match its authority's ordered tip member")
    return binding


def _change_scope(
    change: dict[str, Any], members: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    impact = _require_string(change.get("impact"), "change.impact")
    if impact not in IMPACTS:
        raise RoutingInputError(f"change.impact must be one of {sorted(IMPACTS)}")
    invariants = _require_list(change.get("invariants"), "change.invariants")
    if any(not isinstance(item, str) or not item.strip() for item in invariants):
        raise RoutingInputError("change.invariants must contain non-empty strings")
    if not invariants:
        raise RoutingInputError("change.invariants must not be empty")
    affected = _require_list(change.get("affected_members"), "change.affected_members")
    if any(not isinstance(item, str) or not item.strip() for item in affected):
        raise RoutingInputError("change.affected_members must contain non-empty strings")

    flags = {flag: _require_bool(change.get(flag), f"change.{flag}") for flag in EXPANSION_FLAGS}
    whole_stack = any(flags.values()) or impact in {"unbounded", "unknown"}
    if not affected:
        affected = [member["id"] for member in members]
    known_ids = {member["id"] for member in members}
    unknown_ids = sorted(set(affected) - known_ids)
    if unknown_ids:
        raise RoutingInputError(
            "change.affected_members contains members absent from candidate.members: "
            + ", ".join(unknown_ids)
        )

    # Member topology remains ordered in the candidate binding. Selection is a set,
    # projected in that canonical order; invariant order carries no scope meaning.
    selected_members = [
        member["id"] for member in members if whole_stack or member["id"] in affected
    ]
    scope = {
        "kind": "whole-stack" if whole_stack else "delta",
        "members": selected_members,
        "invariants": sorted(set(invariants)),
        "impact": impact,
        **flags,
    }
    reasons: list[str] = []
    if impact == "unknown":
        reasons.append("impact_unknown")
    elif impact == "unbounded":
        reasons.append("impact_unbounded")
    if flags["contract_changed"]:
        reasons.append("shared_contract_changed")
    if flags["trust_boundary_changed"]:
        reasons.append("trust_boundary_changed")
    if flags["topology_changed"]:
        reasons.append("dependency_topology_changed")
    if flags["cross_member_interaction_changed"]:
        reasons.append("cross_member_interaction_changed")
    if not reasons:
        reasons.append("bounded_impact_closure")
    return scope, reasons


def _request_binding(
    packet: dict[str, Any],
    binding: dict[str, Any],
    input_binding: dict[str, Any],
) -> dict[str, Any]:
    purpose = _require_string(packet.get("purpose"), "purpose")
    objective = _require_string(packet.get("objective"), "objective")
    contract = _require_object(packet.get("contract"), "contract")
    if not contract:
        raise RoutingInputError("contract must explicitly identify the review contract")
    _validate_json_data(contract, "contract")
    return {
        "repository": binding["repository"],
        "objective": objective,
        "purpose": purpose,
        "candidate": binding,
        "contract": contract,
        "input_binding": input_binding,
    }


def _binding_key(
    packet: dict[str, Any],
    binding: dict[str, Any],
    input_binding: dict[str, Any],
) -> str:
    return _digest(_request_binding(packet, binding, input_binding))


def _request_key(
    packet: dict[str, Any],
    binding: dict[str, Any],
    scope: dict[str, Any],
    input_binding: dict[str, Any],
) -> str:
    material = _request_binding(packet, binding, input_binding)
    material["scope"] = scope
    return _digest(material)


def _stable_request_binding(value: Any) -> dict[str, Any] | None:
    """Remove only mutable routing state from a persisted request binding."""

    if not isinstance(value, dict) or not _is_json_data(value):
        return None
    return {key: item for key, item in value.items() if key != "review_readiness"}


def _recorded_scope_key_matches(record: dict[str, Any], scope_field: str) -> bool:
    """Validate current and legacy request keys for one recorded scope."""

    recorded = record.get("request_binding")
    scope = record.get(scope_field)
    if not isinstance(recorded, dict) or not isinstance(scope, dict):
        return False
    stable = _stable_request_binding(recorded)
    if stable is None:
        return False
    valid_keys = {
        _digest({**recorded, "scope": scope}),
        _digest({**stable, "scope": scope}),
    }
    return record.get("key") in valid_keys


def _scope_dominates(prior: Any, current: dict[str, Any]) -> bool:
    """Require explicit semantic scope, in addition to actual result coverage."""
    if not isinstance(prior, dict):
        return False
    if not isinstance(prior.get("kind"), str) or prior["kind"] not in {"delta", "whole-stack"}:
        return False
    if not isinstance(prior.get("impact"), str) or prior["impact"] not in IMPACTS:
        return False
    for flag in EXPANSION_FLAGS:
        if type(prior.get(flag)) is not bool:
            return False
        if current[flag] and not prior[flag]:
            return False
    if current["kind"] == "whole-stack" and prior["kind"] != "whole-stack":
        return False
    # Unknown and unbounded impact are distinct claims; neither proves the other.
    if current["impact"] != "bounded" and prior["impact"] != current["impact"]:
        return False
    if prior["kind"] == "delta" and (
        prior["impact"] != "bounded" or any(prior[flag] for flag in EXPANSION_FLAGS)
    ):
        return False
    for field in ("members", "invariants"):
        values = prior.get(field)
        if not isinstance(values, list) or not values:
            return False
        if any(not isinstance(value, str) or not value.strip() for value in values):
            return False
        if set(current[field]) - set(values):
            return False
    return True


def _record_request_binding_matches(record: dict[str, Any], current: dict[str, Any]) -> bool:
    recorded = record.get("request_binding")
    if not isinstance(recorded, dict) or not _is_json_data(recorded):
        return False
    digest = _digest(recorded)
    stable = _stable_request_binding(recorded)
    if (
        record.get("request_binding_digest") != digest
        or stable is None
        or _digest(stable) != _digest(current)
    ):
        return False
    # Reject contradictory legacy mirror metadata rather than silently choosing
    # the convenient copy. The nested binding is the complete canonical material.
    for field in ("repository", "objective", "purpose", "contract"):
        if field in record and (
            not _is_json_data(record[field]) or _digest(record[field]) != _digest(current[field])
        ):
            return False
    return True


def _review_covers(
    review: dict[str, Any],
    *,
    key: str,
    binding_key: str,
    purpose: str,
    scope: dict[str, Any],
    candidate_binding: dict[str, Any],
    input_binding: dict[str, Any],
    request_binding: dict[str, Any],
) -> bool:
    if review.get("status") != "completed":
        return False
    same_scope_request = review.get("key") == key
    broader_scope_result = review.get("binding_key") == binding_key
    if not _record_request_binding_matches(review, request_binding):
        return False
    if not same_scope_request and not broader_scope_result:
        if not _recorded_scope_key_matches(review, "reviewed_scope"):
            return False
    if not _scope_dominates(review.get("reviewed_scope"), scope):
        return False
    if (
        purpose == "merge_acceptance"
        and (len(scope["members"]) > 1 or len(review["reviewed_scope"]["members"]) > 1)
        and "integration_base_tree_sha" not in candidate_binding
    ):
        return False
    if review.get("independent") is not True:
        return False
    if review.get("metadata_complete") is not True:
        return False
    if review.get("pagination_complete") is not True:
        return False
    binding = review.get("candidate_binding")
    if (
        not isinstance(binding, dict)
        or not _is_json_data(binding)
        or review.get("candidate_binding_digest") != _digest(binding)
        or review.get("candidate_binding_digest") != _digest(candidate_binding)
    ):
        return False
    review_input_binding = review.get("input_binding")
    if (
        not isinstance(review_input_binding, dict)
        or not _is_json_data(review_input_binding)
        or review.get("input_binding_digest") != _digest(review_input_binding)
        or review.get("input_binding_digest") != _digest(input_binding)
    ):
        return False
    coverage = review.get("coverage")
    if not isinstance(coverage, dict):
        return False

    def _string_list(value: Any) -> list[str] | None:
        if not isinstance(value, list):
            return None
        if any(not isinstance(item, str) or not item.strip() for item in value):
            return None
        return value

    purposes = _string_list(coverage.get("purposes", [review.get("purpose")]))
    members = _string_list(coverage.get("members", []))
    invariants = _string_list(coverage.get("invariants", []))
    limitations = _string_list(coverage.get("limitations"))
    if purposes is None or members is None or invariants is None or limitations is None:
        return False
    if (
        purpose == "merge_acceptance"
        and len(members) > 1
        and "integration_base_tree_sha" not in candidate_binding
    ):
        return False
    if purpose not in purposes:
        return False
    if set(scope["members"]) - set(members):
        return False
    if set(scope["invariants"]) - set(invariants):
        return False
    if limitations:
        return False
    return True


def _validate_preflight(packet: dict[str, Any]) -> list[str]:
    raw_preflight = packet.get("preflight")
    if raw_preflight is None:
        return ["preflight_missing"]
    preflight = _require_object(raw_preflight, "preflight")
    if "status" not in preflight:
        return ["preflight_status_missing"]
    status = _require_string(preflight["status"], "preflight.status")
    if status not in {"ready", "unknown", "failed"}:
        raise RoutingInputError("preflight.status must be ready, unknown, or failed")
    missing = preflight.get("missing", [])
    if not isinstance(missing, list) or any(not isinstance(item, str) for item in missing):
        raise RoutingInputError("preflight.missing must be a list of strings")
    if status != "ready":
        return [f"preflight_{status}", *missing]
    return missing


def _discovery_missing(packet: dict[str, Any]) -> list[str]:
    missing = [f"{field}_not_observed" for field in ("requests", "reviews") if field not in packet]
    discovery = packet.get("discovery")
    if not isinstance(discovery, dict):
        return [*missing, "discovery_completeness_unknown"]
    for field in ("requests_complete", "reviews_complete"):
        if discovery.get(field) is not True:
            missing.append(f"{field}_not_established")
    return missing


def _active_request_matches(
    item: dict[str, Any],
    binding: dict[str, Any],
    inputs: dict[str, Any],
    request_binding: dict[str, Any],
    scope: dict[str, Any],
    key: str,
) -> bool:
    if not _record_request_binding_matches(item, request_binding):
        return False
    requested_scope = item.get("requested_scope")
    if not isinstance(requested_scope, dict) or not _is_json_data(requested_scope):
        return False
    if not _scope_dominates(requested_scope, scope):
        return False
    if not _recorded_scope_key_matches(item, "requested_scope"):
        return False
    for field, current in (("candidate_binding", binding), ("input_binding", inputs)):
        value = item.get(field)
        if not isinstance(value, dict) or not _is_json_data(value):
            return False
        if item.get(field + "_digest") != _digest(value) or _digest(value) != _digest(current):
            return False
    return True


def plan(packet: dict[str, Any]) -> dict[str, Any]:
    if type(packet.get("schema_version")) is not int or packet["schema_version"] != SCHEMA_VERSION:
        raise RoutingInputError("unsupported review-routing packet schema")
    purpose = _require_string(packet.get("purpose"), "purpose")
    if purpose not in PURPOSES:
        raise RoutingInputError(f"purpose must be one of {sorted(PURPOSES)}")
    _require_string(packet.get("objective"), "objective")
    options = _require_object(packet.get("options", {}), "options")
    early = options.get("early_diagnostic", False)
    if type(early) is not bool:
        raise RoutingInputError("options.early_diagnostic must be a boolean")
    if early and purpose == "merge_acceptance":
        raise RoutingInputError("early diagnostic cannot use merge_acceptance purpose")

    candidate = _require_object(packet.get("candidate"), "candidate")
    binding = _candidate_binding(candidate)
    input_binding = _input_binding(packet)
    review_readiness = normalize_review_readiness(packet.get("review_readiness"))
    change = _require_object(packet.get("change"), "change")
    scope, reasons = _change_scope(change, candidate["members"])
    request_binding = _request_binding(packet, binding, input_binding)
    binding_key = _binding_key(packet, binding, input_binding)
    key = _request_key(packet, binding, scope, input_binding)
    missing = [*_validate_preflight(packet), *_discovery_missing(packet)]
    if (
        purpose == "merge_acceptance"
        and len(scope["members"]) > 1
        and "integration_base_tree_sha" not in binding
    ):
        missing.append("cumulative_integration_base_tree_missing")

    reviews = _require_list(packet.get("reviews", []), "reviews")
    requests = _require_list(packet.get("requests", []), "requests")
    for index, item in enumerate(reviews):
        _require_object(item, f"reviews[{index}]")
        status = _require_string(item.get("status"), f"reviews[{index}].status")
        if status not in RESULT_STATES:
            raise RoutingInputError(f"reviews[{index}].status is invalid")
    for index, item in enumerate(requests):
        _require_object(item, f"requests[{index}]")
        status = _require_string(item.get("status"), f"requests[{index}].status")
        if status not in RESULT_STATES:
            raise RoutingInputError(f"requests[{index}].status is invalid")

    base_result = {
        "schema_version": SCHEMA_VERSION,
        "binding_key": binding_key,
        "request_key": key,
        "request_binding": request_binding,
        "request_binding_digest": _digest(request_binding),
        "input_binding_digest": _digest(input_binding),
        "selected_scope": scope,
        "reusable_evidence": [],
        "missing_confirmation": list(missing),
        "unknowns": [],
        "request_state": "not_requested",
        "merge_authorization": "not_established",
        "review_readiness": review_readiness,
        "review_readiness_digest": _digest(review_readiness),
        "review_acquisition_allowed": review_readiness["review_acquisition_allowed"],
    }

    if missing:
        return {
            **base_result,
            "action": ACTION_MISSING,
            "reason": ["required_precondition_missing", *reasons],
            "unknowns": list(missing),
        }

    matching = []
    for item in requests:
        if item["status"] == "not_requested":
            continue
        same_binding = item.get("binding_key") == binding_key or _record_request_binding_matches(
            item, request_binding
        )
        prior_scope = item.get("requested_scope")
        # Unknown scope in the same binding lineage must be reconciled, not
        # silently discarded. Valid narrower/disjoint requests cannot supply
        # this scope and therefore do not supersede its evidence.
        scope_unknown = not isinstance(prior_scope, dict) or not _is_json_data(prior_scope)
        if not scope_unknown:
            scope_unknown = not _scope_dominates(prior_scope, prior_scope)
        if item.get("key") == key or (
            same_binding and (scope_unknown or _scope_dominates(prior_scope, scope))
        ):
            matching.append(item)
    latest = packet["discovery"].get("latest_request_cycle")
    cycle_ids = [item.get("cycle_id") for item in matching]
    if matching or latest is not None:
        if (
            not isinstance(latest, str)
            or not latest.strip()
            or any(not isinstance(c, str) or not c.strip() for c in cycle_ids)
            or len(set(cycle_ids)) != len(cycle_ids)
            or latest not in cycle_ids
        ):
            return {
                **base_result,
                "action": ACTION_MISSING,
                "reason": ["latest_request_cycle_unknown"],
                "missing_confirmation": ["explicit_latest_applicable_provider_cycle"],
            }
        matching = [item for item in matching if item["cycle_id"] == latest]

    for item in matching:
        locator = item.get("handle") or item.get("locator")
        if not _active_request_matches(
            item, binding, input_binding, request_binding, scope, key
        ) or not (isinstance(locator, str) and locator.strip()):
            return {
                **base_result,
                "action": ACTION_MISSING,
                "reason": ["active_request_binding_or_locator_unknown"],
                "request_state": item["status"],
                "missing_confirmation": ["current_provider_request_binding_and_locator"],
            }
        if item.get("status") in {
            "in_progress",
            "submission_unknown",
        }:
            return {
                **base_result,
                "action": ACTION_RECONCILE,
                "reason": ["same_request_already_active"],
                "request_state": item["status"],
                "reusable_evidence": [locator],
            }
        if item["status"] != "completed":
            return {
                **base_result,
                "action": ACTION_MISSING,
                "request_state": item["status"],
                "reason": ["latest_request_cycle_unresolved"],
                "missing_confirmation": ["disposition_latest_provider_cycle"],
            }

    for item in reviews:
        if matching and item.get("cycle_id") != latest:
            continue
        if not isinstance(item.get("locator"), str) or not item["locator"].strip():
            continue
        if _review_covers(
            item,
            key=key,
            binding_key=binding_key,
            purpose=purpose,
            scope=scope,
            candidate_binding=binding,
            input_binding=input_binding,
            request_binding=request_binding,
        ):
            return {
                **base_result,
                "action": ACTION_REUSE,
                "reason": ["explicit_coverage_satisfies_scope"],
                "request_state": "completed",
                "reusable_evidence": [item["locator"]],
            }

    if matching:
        return {
            **base_result,
            "action": ACTION_MISSING,
            "request_state": "completed",
            "reason": ["latest_cycle_result_not_applicable"],
            "missing_confirmation": ["locate_and_verify_latest_cycle_result"],
        }
    if early:
        if not review_readiness["review_acquisition_allowed"]:
            reasons = [
                "review_readiness_incomplete",
                *review_readiness["reasons"],
            ]
            return {
                **base_result,
                "action": ACTION_MISSING,
                "reason": reasons,
                "missing_confirmation": reasons[1:],
            }
        return {
            **base_result,
            "action": ACTION_EARLY,
            "reason": ["explicit_early_diagnostic", *reasons],
        }

    if scope["kind"] == "whole-stack":
        action = ACTION_STACK
        reason = ["related_scope_required", *reasons]
    else:
        action = ACTION_DELTA
        reason = ["new_or_inapplicable_exact_head", *reasons]
    if not review_readiness["review_acquisition_allowed"]:
        blocked_reasons = [
            "review_readiness_incomplete",
            *review_readiness["reasons"],
        ]
        return {
            **base_result,
            "action": ACTION_MISSING,
            "reason": blocked_reasons,
            "missing_confirmation": blocked_reasons[1:],
        }
    return {**base_result, "action": action, "reason": reason}


def _load_packet(path: str) -> dict[str, Any]:
    if path == "-":
        payload = sys.stdin.read()
    else:
        payload = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RoutingInputError(f"invalid JSON input: {exc}") from exc
    return _require_object(value, "packet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON packet path, or '-' for stdin")
    args = parser.parse_args(argv)
    try:
        result = plan(_load_packet(args.input))
    except (OSError, RoutingInputError) as exc:
        print(f"ERROR REVIEW_ROUTING: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
