#!/usr/bin/env python3
"""Select the next review action from an explicit, immutable review packet.

This helper is deliberately read-only.  It does not inspect a repository, call a
provider, submit a review, or establish merge authorization.  The maintenance
Skill supplies the live facts and the shared merge gate remains authoritative for
review evidence and acceptance.
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
        return all(
            isinstance(key, str) and _is_json_data(item)
            for key, item in value.items()
        )
    return False


def _validate_json_data(value: Any, name: str) -> Any:
    if not _is_json_data(value):
        raise RoutingInputError(f"{name} must be JSON data")
    return value


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

    contract_changed = _require_bool(
        change.get("contract_changed", False), "change.contract_changed"
    )
    trust_boundary_changed = _require_bool(
        change.get("trust_boundary_changed", False), "change.trust_boundary_changed"
    )
    topology_changed = _require_bool(
        change.get("topology_changed", False), "change.topology_changed"
    )
    broad_flags = (
        contract_changed,
        trust_boundary_changed,
        topology_changed,
        impact in {"unbounded", "unknown"},
    )
    whole_stack = any(broad_flags)
    if not affected:
        affected = [member["id"] for member in members]
    known_ids = {member["id"] for member in members}
    unknown_ids = sorted(set(affected) - known_ids)
    if unknown_ids:
        raise RoutingInputError(
            "change.affected_members contains members absent from candidate.members: "
            + ", ".join(unknown_ids)
        )

    selected_members = [member["id"] for member in members] if whole_stack else affected
    scope = {
        "kind": "whole-stack" if whole_stack else "delta",
        "members": selected_members,
        "invariants": list(invariants),
        "impact": impact,
        "contract_changed": contract_changed,
        "trust_boundary_changed": trust_boundary_changed,
        "topology_changed": topology_changed,
    }
    reasons: list[str] = []
    if impact == "unknown":
        reasons.append("impact_unknown")
    elif impact == "unbounded":
        reasons.append("impact_unbounded")
    if contract_changed:
        reasons.append("shared_contract_changed")
    if trust_boundary_changed:
        reasons.append("trust_boundary_changed")
    if topology_changed:
        reasons.append("dependency_topology_changed")
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
    contract = packet.get("contract", {})
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


def _scope_dominates(prior: Any, current: dict[str, Any]) -> bool:
    """Require explicit semantic scope, in addition to actual result coverage."""
    if not isinstance(prior, dict):
        return False
    if not isinstance(prior.get("kind"), str) or prior["kind"] not in {"delta", "whole-stack"}:
        return False
    if not isinstance(prior.get("impact"), str) or prior["impact"] not in IMPACTS:
        return False
    for flag in ("contract_changed", "trust_boundary_changed", "topology_changed"):
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
        prior["impact"] != "bounded"
        or any(prior[flag] for flag in (
            "contract_changed", "trust_boundary_changed", "topology_changed"
        ))
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


def _review_covers(
    review: dict[str, Any],
    *,
    key: str,
    binding_key: str,
    purpose: str,
    scope: dict[str, Any],
    candidate_binding: dict[str, Any],
    input_binding: dict[str, Any],
) -> bool:
    if review.get("status") != "completed":
        return False
    same_scope_request = review.get("key") == key
    broader_scope_result = review.get("binding_key") == binding_key
    if not same_scope_request and not broader_scope_result:
        return False
    if not _scope_dominates(review.get("reviewed_scope"), scope):
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
        or review.get("candidate_binding_digest") != _digest(binding)
        or review.get("candidate_binding_digest") != _digest(candidate_binding)
    ):
        return False
    review_input_binding = review.get("input_binding")
    if (
        not isinstance(review_input_binding, dict)
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
    limitations = _string_list(coverage.get("limitations", []))
    if purposes is None or members is None or invariants is None or limitations is None:
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
    status = preflight["status"]
    if status not in {"ready", "unknown", "failed"}:
        raise RoutingInputError("preflight.status must be ready, unknown, or failed")
    missing = preflight.get("missing", [])
    if not isinstance(missing, list) or any(not isinstance(item, str) for item in missing):
        raise RoutingInputError("preflight.missing must be a list of strings")
    if status != "ready":
        return [f"preflight_{status}", *missing]
    return missing


def plan(packet: dict[str, Any]) -> dict[str, Any]:
    if packet.get("schema_version") != SCHEMA_VERSION:
        raise RoutingInputError("unsupported review-routing packet schema")
    purpose = _require_string(packet.get("purpose"), "purpose")
    if purpose not in PURPOSES:
        raise RoutingInputError(f"purpose must be one of {sorted(PURPOSES)}")
    _require_string(packet.get("objective"), "objective")

    candidate = _require_object(packet.get("candidate"), "candidate")
    binding = _candidate_binding(candidate)
    input_binding = _input_binding(packet)
    change = _require_object(packet.get("change"), "change")
    scope, reasons = _change_scope(change, candidate["members"])
    binding_key = _binding_key(packet, binding, input_binding)
    key = _request_key(packet, binding, scope, input_binding)
    missing = _validate_preflight(packet)

    reviews = _require_list(packet.get("reviews", []), "reviews")
    requests = _require_list(packet.get("requests", []), "requests")
    for index, item in enumerate(reviews):
        _require_object(item, f"reviews[{index}]")
        status = item.get("status")
        if status not in RESULT_STATES:
            raise RoutingInputError(f"reviews[{index}].status is invalid")
    for index, item in enumerate(requests):
        _require_object(item, f"requests[{index}]")
        status = item.get("status")
        if status not in RESULT_STATES:
            raise RoutingInputError(f"requests[{index}].status is invalid")

    base_result = {
        "schema_version": SCHEMA_VERSION,
        "binding_key": binding_key,
        "request_key": key,
        "input_binding_digest": _digest(input_binding),
        "selected_scope": scope,
        "reusable_evidence": [],
        "missing_confirmation": list(missing),
        "unknowns": [],
        "request_state": "not_requested",
        "merge_authorization": "not_established",
    }

    if missing:
        return {
            **base_result,
            "action": ACTION_MISSING,
            "reason": ["required_precondition_missing", *reasons],
            "unknowns": list(missing),
        }

    for item in requests:
        if item.get("key") == key and item.get("status") in {
            "in_progress",
            "submission_unknown",
        }:
            return {
                **base_result,
                "action": ACTION_RECONCILE,
                "reason": ["same_request_already_active"],
                "request_state": item["status"],
                "reusable_evidence": [item.get("handle") or item.get("locator") or key],
            }

    for item in reviews:
        if _review_covers(
            item,
            key=key,
            binding_key=binding_key,
            purpose=purpose,
            scope=scope,
            candidate_binding=binding,
            input_binding=input_binding,
        ):
            return {
                **base_result,
                "action": ACTION_REUSE,
                "reason": ["explicit_coverage_satisfies_scope"],
                "request_state": "completed",
                "reusable_evidence": [item.get("locator") or key],
            }

    options = _require_object(packet.get("options", {}), "options")
    if options.get("early_diagnostic") is True:
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
