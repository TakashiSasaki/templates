from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "repository-skills" / "land-templates-stack" / "scripts" / "plan_review_scope.py"
)
SPEC = importlib.util.spec_from_file_location("plan_review_scope", MODULE_PATH)
assert SPEC and SPEC.loader
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def _sha(letter: str) -> str:
    return letter * 40


def _packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 2,
        "objective": "adaptive review routing",
        "purpose": "whole_stack_diagnostic",
        "candidate": {
            "repository": "TakashiSasaki/templates",
            "authority": "policy",
            "base_sha": _sha("a"),
            "effective_base_sha": _sha("a"),
            "head_sha": _sha("b"),
            "members": [
                {
                    "id": "policy-p1",
                    "authority": "policy",
                    "base_sha": _sha("a"),
                    "head_sha": _sha("b"),
                },
                {
                    "id": "composition-c",
                    "authority": "composition",
                    "base_sha": _sha("c"),
                    "head_sha": _sha("d"),
                },
            ],
        },
        "change": {
            "impact": "bounded",
            "invariants": ["review-scope"],
            "affected_members": ["policy-p1"],
            "contract_changed": False,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        },
        "input_binding": {
            "provider": "codex",
            "contract_revision": "review-contract-1",
            "evidence": {"ci": ["run-1"], "findings": []},
        },
        "preflight": {"status": "ready", "missing": []},
        "reviews": [],
        "requests": [],
        "discovery": {"requests_complete": True, "reviews_complete": True},
        "options": {},
    }
    packet.update(overrides)
    return packet


def _binding(packet: dict[str, object]) -> dict[str, object]:
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    return {
        "repository": candidate["repository"],
        "authority": candidate["authority"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "head_sha": candidate["head_sha"],
        "members": candidate["members"],
    }


def _key(packet: dict[str, object]) -> str:
    initial = planner.plan(packet)
    return initial["request_key"]


@pytest.mark.parametrize(
    "authority,invariant",
    [
        ("policy", "normative-routing"),
        ("composition", "transaction-ownership"),
        ("integration", "bundle-transport"),
        ("modeling", "record-provenance"),
        ("site", "browser-artifact"),
    ],
)
def test_each_authority_routes_bounded_expanded_and_reusable_scope(
    authority: str, invariant: str
) -> None:
    member_id = f"{authority}-maintenance"
    packet = _packet(purpose="fix_verification")
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    candidate["authority"] = authority
    candidate["members"] = [
        {
            "id": member_id,
            "authority": authority,
            "base_sha": _sha("a"),
            "head_sha": _sha("b"),
        }
    ]
    packet["change"] = {
        "impact": "bounded",
        "invariants": [invariant],
        "affected_members": [member_id],
        "contract_changed": False,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }

    bounded = planner.plan(packet)
    assert bounded["action"] == planner.ACTION_DELTA
    assert bounded["selected_scope"]["members"] == [member_id]

    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": bounded["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": [member_id],
                "invariants": [invariant],
                "limitations": [],
            },
            "locator": f"{authority}-review",
        }
    ]
    reused = planner.plan(packet)
    assert reused["action"] == planner.ACTION_REUSE
    assert reused["reusable_evidence"] == [f"{authority}-review"]

    packet["change"] = {
        "impact": "bounded",
        "invariants": [invariant, "shared-contract"],
        "affected_members": [member_id],
        "contract_changed": True,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }
    expanded = planner.plan(packet)
    assert expanded["action"] == planner.ACTION_STACK
    assert expanded["selected_scope"]["kind"] == "whole-stack"


def test_bounded_change_selects_independent_delta_scope() -> None:
    packet = _packet(purpose="fix_verification")
    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["selected_scope"]["kind"] == "delta"
    assert result["selected_scope"]["members"] == ["policy-p1"]
    assert result["merge_authorization"] == "not_established"


@pytest.mark.parametrize(
    "flag",
    [
        "contract_changed",
        "trust_boundary_changed",
        "topology_changed",
        "cross_member_interaction_changed",
    ],
)
def test_prior_delta_cannot_cover_semantic_expansion(flag: str) -> None:
    prior = planner.plan(_packet())["selected_scope"]
    current = dict(prior, kind="whole-stack", **{flag: True})
    assert not planner._scope_dominates(prior, current)
    # Even a whole-stack result needs the particular expansion property.
    assert not planner._scope_dominates(dict(prior, kind="whole-stack"), current)
    assert planner._scope_dominates(current, prior)


@pytest.mark.parametrize("prior", [None, {}, {"kind": []}, {"kind": "whole-stack"}])
def test_unknown_prior_scope_fails_closed(prior: object) -> None:
    assert not planner._scope_dominates(prior, planner.plan(_packet())["selected_scope"])


def test_duplicate_candidate_ids_fail_closed() -> None:
    packet = _packet()
    packet["candidate"]["members"][1]["id"] = "policy-p1"
    with pytest.raises(planner.RoutingInputError, match="unique"):
        planner.plan(packet)


def test_impact_expansion_requires_applicable_prior_scope() -> None:
    prior = planner.plan(_packet())["selected_scope"]
    for impact in ("unknown", "unbounded"):
        assert not planner._scope_dominates(prior, dict(prior, kind="whole-stack", impact=impact))


@pytest.mark.parametrize(
    "change",
    [
        {"impact": "unbounded", "contract_changed": False},
        {"impact": "unknown", "contract_changed": False},
        {"impact": "bounded", "contract_changed": True},
        {"impact": "bounded", "trust_boundary_changed": True},
        {"impact": "bounded", "topology_changed": True},
    ],
)
def test_shared_or_unknown_impact_expands_related_stack(change: dict[str, object]) -> None:
    packet = _packet(
        change={
            "invariants": ["review-scope"],
            "affected_members": ["policy-p1"],
            "contract_changed": False,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
            **change,
        }
    )
    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["selected_scope"]["members"] == ["policy-p1", "composition-c"]


def _active_request(packet, key, status, **locator):
    binding = _binding(packet)
    return {
        "key": key,
        "status": status,
        **locator,
        "candidate_binding": binding,
        "candidate_binding_digest": planner._digest(binding),
        "input_binding": packet["input_binding"],
        "input_binding_digest": planner._digest(packet["input_binding"]),
    }


def test_existing_inflight_request_is_reconciled_without_resubmission() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [_active_request(packet, key, "in_progress", handle="review-42")]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_RECONCILE
    assert result["reusable_evidence"] == ["review-42"]


def test_submission_unknown_is_reconciled_before_retry() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [_active_request(packet, key, "submission_unknown", locator="comment-9")]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_RECONCILE
    assert result["request_state"] == "submission_unknown"


def test_explicit_coverage_reuses_completed_independent_result() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            "purpose": "whole_stack_diagnostic",
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": ["whole_stack_diagnostic"],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
            "locator": "review-17",
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_REUSE
    assert result["reusable_evidence"] == ["review-17"]


def test_broader_completed_coverage_reuses_for_narrower_scope() -> None:
    packet = _packet(purpose="merge_acceptance")
    broad = _packet(
        purpose="merge_acceptance",
        change={
            "impact": "bounded",
            "invariants": ["review-scope", "shared-contract"],
            "affected_members": ["policy-p1", "composition-c"],
            "contract_changed": True,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        },
    )
    broad_result = planner.plan(broad)
    binding = _binding(broad)
    packet["reviews"] = [
        {
            "key": broad_result["request_key"],
            "binding_key": broad_result["binding_key"],
            "status": "completed",
            "purpose": "merge_acceptance",
            "reviewed_scope": broad_result["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": broad["input_binding"],
            "input_binding_digest": planner._digest(broad["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": ["merge_acceptance"],
                "members": ["policy-p1", "composition-c"],
                "invariants": ["review-scope", "shared-contract"],
                "limitations": [],
            },
            "locator": "broad-review-18",
        }
    ]

    result = planner.plan(packet)

    assert result["selected_scope"]["kind"] == "delta"
    assert result["action"] == planner.ACTION_REUSE
    assert result["reusable_evidence"] == ["broad-review-18"]


@pytest.mark.parametrize("status", ["partial", "failed", "applicability_unknown", "stale"])
def test_incomplete_review_result_does_not_establish_coverage(status: str) -> None:
    packet = _packet()
    initial = planner.plan(packet)
    packet["reviews"] = [{"key": initial["request_key"], "status": status}]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["reusable_evidence"] == []


def test_missing_or_unknown_preflight_stops_before_review_acquisition() -> None:
    packet = _packet(preflight={"status": "unknown", "missing": ["ordered-members"]})

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_MISSING
    assert "ordered-members" in result["unknowns"]


def test_omitted_preflight_or_status_stops_before_review_acquisition() -> None:
    for preflight, expected in (
        (None, "preflight_missing"),
        ({"missing": []}, "preflight_status_missing"),
    ):
        packet = _packet()
        if preflight is None:
            packet.pop("preflight")
        else:
            packet["preflight"] = preflight

        result = planner.plan(packet)

        assert result["action"] == planner.ACTION_MISSING
        assert expected in result["unknowns"]


def test_early_diagnostic_requires_explicit_selection() -> None:
    packet = _packet(options={"early_diagnostic": True})

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_EARLY


def test_request_key_is_not_head_only() -> None:
    packet = _packet()
    changed = _packet(objective="different objective")

    assert _key(packet) != _key(changed)


def test_request_key_includes_validated_input_binding() -> None:
    packet = _packet()
    changed = _packet(
        input_binding={
            "provider": "codex",
            "contract_revision": "review-contract-1",
            "evidence": {"ci": ["run-2"], "findings": []},
        }
    )

    assert _key(packet) != _key(changed)


def test_completed_review_with_stale_candidate_binding_is_not_reused() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    stale_binding = _binding(packet)
    stale_binding["head_sha"] = _sha("c")
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
            "candidate_binding": stale_binding,
            "candidate_binding_digest": planner._digest(stale_binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_completed_review_with_changed_input_binding_is_not_reused() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    old_input_binding = packet["input_binding"]
    packet["input_binding"] = {
        "provider": "codex",
        "contract_revision": "review-contract-1",
        "evidence": {"ci": ["run-2"], "findings": []},
    }
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
            "candidate_binding": _binding(packet),
            "candidate_binding_digest": planner._digest(_binding(packet)),
            "input_binding": old_input_binding,
            "input_binding_digest": planner._digest(old_input_binding),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_completed_review_with_json_type_distinct_input_is_not_reused() -> None:
    packet = _packet(
        input_binding={
            "provider": "codex",
            "flag": True,
        }
    )
    initial = planner.plan(packet)
    old_input_binding = {"provider": "codex", "flag": 1}
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
            "candidate_binding": _binding(packet),
            "candidate_binding_digest": planner._digest(_binding(packet)),
            "input_binding": old_input_binding,
            "input_binding_digest": planner._digest(old_input_binding),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_same_head_new_contract_evidence_allows_additional_related_scope() -> None:
    packet = _packet()
    previous = planner.plan(packet)
    packet["reviews"] = [
        {
            "key": previous["request_key"],
            "status": "completed",
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
        }
    ]
    packet["change"] = {
        "impact": "bounded",
        "invariants": ["review-scope", "shared-contract"],
        "affected_members": ["policy-p1"],
        "contract_changed": True,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["request_key"] != previous["request_key"]


def test_multiple_prior_whole_stack_results_do_not_create_a_numeric_cap() -> None:
    packet = _packet(
        change={
            "impact": "bounded",
            "invariants": ["shared-contract"],
            "affected_members": ["policy-p1"],
            "contract_changed": True,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        }
    )
    initial = planner.plan(packet)
    packet["reviews"] = [
        {"key": "old-whole-stack-1", "status": "completed"},
        {"key": "old-whole-stack-2", "status": "completed"},
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["request_key"] == initial["request_key"]


@pytest.mark.parametrize(
    "field",
    [
        "contract_changed",
        "trust_boundary_changed",
        "topology_changed",
        "cross_member_interaction_changed",
    ],
)
@pytest.mark.parametrize("value", [1, "true", None])
def test_non_boolean_scope_flag_fails_closed(field: str, value: object) -> None:
    change = _packet()["change"]
    assert isinstance(change, dict)
    change[field] = value

    with pytest.raises(planner.RoutingInputError, match="must be a boolean"):
        planner.plan(_packet(change=change))


def test_invalid_candidate_binding_fails_closed() -> None:
    packet = _packet()
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    candidate["head_sha"] = "main"

    with pytest.raises(planner.RoutingInputError, match="full Git SHA"):
        planner.plan(packet)


def test_missing_input_binding_fails_closed() -> None:
    packet = _packet()
    del packet["input_binding"]

    with pytest.raises(planner.RoutingInputError, match="input_binding must be an object"):
        planner.plan(packet)


def test_empty_invariant_scope_fails_closed() -> None:
    change = _packet()["change"]
    assert isinstance(change, dict)
    change["invariants"] = []

    with pytest.raises(planner.RoutingInputError, match="must not be empty"):
        planner.plan(_packet(change=change))


@pytest.mark.parametrize("field", ["purposes", "members", "invariants", "limitations"])
def test_malformed_coverage_lists_are_not_reused(field: str) -> None:
    packet = _packet()
    initial = planner.plan(packet)
    binding = _binding(packet)
    coverage: dict[str, object] = {
        "purposes": [packet["purpose"]],
        "members": ["policy-p1"],
        "invariants": ["review-scope"],
        "limitations": [],
    }
    coverage[field] = {"policy-p1": False}
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": coverage,
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


@pytest.mark.parametrize("field", planner.EXPANSION_FLAGS)
def test_missing_scope_expansion_flag_fails_closed(field: str) -> None:
    packet = _packet()
    del packet["change"][field]
    with pytest.raises(planner.RoutingInputError, match="must be a boolean"):
        planner.plan(packet)


def test_cross_member_interaction_expands_and_invalidates_delta_scope() -> None:
    packet = _packet()
    prior = planner.plan(packet)
    packet["change"]["cross_member_interaction_changed"] = True
    current = planner.plan(packet)
    assert current["action"] == planner.ACTION_STACK
    assert current["selected_scope"]["members"] == ["policy-p1", "composition-c"]
    assert not planner._scope_dominates(prior["selected_scope"], current["selected_scope"])


def test_set_like_scope_order_and_duplicates_do_not_duplicate_active_request() -> None:
    packet = _packet()
    packet["change"]["invariants"] = ["first", "second"]
    packet["change"]["affected_members"] = ["policy-p1", "composition-c"]
    initial = planner.plan(packet)
    packet["requests"] = [
        _active_request(packet, initial["request_key"], "in_progress", handle="review-42")
    ]
    packet["change"]["invariants"] = ["second", "first", "second"]
    packet["change"]["affected_members"] = ["composition-c", "policy-p1", "policy-p1"]
    result = planner.plan(packet)
    assert result["request_key"] == initial["request_key"]
    assert result["action"] == planner.ACTION_RECONCILE
    # Ordered candidate topology is not a set and must remain binding material.
    packet["candidate"]["members"].reverse()
    assert planner.plan(packet)["request_key"] != initial["request_key"]


@pytest.mark.parametrize("field", ["requests", "reviews", "discovery"])
def test_missing_observed_provider_state_blocks_acquisition(field: str) -> None:
    packet = _packet()
    del packet[field]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("field", ["requests_complete", "reviews_complete"])
@pytest.mark.parametrize("value", [None, False, 1, "true", [], {}])
def test_incomplete_or_malformed_discovery_blocks_acquisition(field: str, value: object) -> None:
    packet = _packet()
    packet["discovery"][field] = value
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("status", ["in_progress", "submission_unknown"])
@pytest.mark.parametrize("field", ["candidate_binding", "input_binding"])
def test_active_request_misassociated_metadata_cannot_suppress_current_review(
    status: str, field: str
) -> None:
    packet = _packet()
    active = copy.deepcopy(_active_request(packet, _key(packet), status, handle="old-review"))
    if field == "candidate_binding":
        active[field]["head_sha"] = _sha("c")
    else:
        active[field]["provider"] = "different-provider"
    active[field + "_digest"] = planner._digest(active[field])
    packet["requests"] = [active]
    result = planner.plan(packet)
    assert result["action"] == planner.ACTION_MISSING
    assert not result["reusable_evidence"]


@pytest.mark.parametrize("value", [None, {}, {"flag": True}])
def test_active_request_requires_exact_json_input_binding(value: object) -> None:
    packet = _packet(input_binding={"flag": 1})
    active = _active_request(packet, _key(packet), "in_progress", handle="review")
    active["input_binding"] = value
    active["input_binding_digest"] = planner._digest(value)
    packet["requests"] = [active]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("locator", [{}, {"handle": ""}, {"locator": " "}, {"handle": 1}])
def test_active_request_requires_actionable_provider_locator(locator: dict) -> None:
    packet = _packet()
    packet["requests"] = [_active_request(packet, _key(packet), "submission_unknown", **locator)]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING
